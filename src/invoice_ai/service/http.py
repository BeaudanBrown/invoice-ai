from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import uvicorn

from ..config import RuntimeConfig
from ..control_plane.models import RequestSource
from ..control_plane.store import ControlPlaneStore
from ..erp.schemas import ToolResponse
from ..execution import execute_tool_request
from .models import (
    ErrorResponse,
    HealthResponse,
    RuntimeDependencyView,
    RuntimeResponse,
    RuntimeServiceView,
    ToolRunRequest,
)


@dataclass(frozen=True)
class ServiceState:
    config: RuntimeConfig
    control_plane: ControlPlaneStore

    def execute(
        self,
        payload: ToolRunRequest,
        *,
        operator_id: str | None,
    ) -> ToolResponse:
        return execute_tool_request(
            config=self.config,
            request=payload.tool_request(),
            source=RequestSource.HTTP,
            write_approval_artifacts=payload.write_approval_artifacts,
            operator_id=operator_id,
        )


def create_app(config: RuntimeConfig | None = None) -> FastAPI:
    runtime_config = config or RuntimeConfig.from_env()
    service_state = ServiceState(
        config=runtime_config,
        control_plane=ControlPlaneStore.from_runtime_config(runtime_config),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        runtime_config.paths.ensure()
        service_state.control_plane.ensure()
        yield

    app = FastAPI(
        title="invoice-ai",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.service_state = service_state

    @app.middleware("http")
    async def attach_request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        payload = ErrorResponse(error="bad_request", message=str(exc))
        return JSONResponse(status_code=400, content=payload.as_dict())

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: ValidationError,
    ) -> JSONResponse:
        payload = ErrorResponse(error="bad_request", message=str(exc))
        return JSONResponse(status_code=400, content=payload.as_dict())

    @app.exception_handler(ValueError)
    async def value_error_handler(
        _request: Request,
        exc: ValueError,
    ) -> JSONResponse:
        payload = ErrorResponse(error="bad_request", message=str(exc))
        return JSONResponse(status_code=400, content=payload.as_dict())

    @app.exception_handler(Exception)
    async def internal_error_handler(
        _request: Request,
        exc: Exception,
    ) -> JSONResponse:
        payload = ErrorResponse(error="internal_error", message=str(exc))
        return JSONResponse(status_code=500, content=payload.as_dict())

    @app.get("/healthz", response_model=HealthResponse, tags=["runtime"])
    async def healthz(
        state: ServiceState = Depends(get_service_state),
    ) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="invoice-ai",
            listen_address=state.config.service.listen_address,
            port=state.config.service.port,
        )

    @app.get("/api/runtime", response_model=RuntimeResponse, tags=["runtime"])
    async def runtime(
        state: ServiceState = Depends(get_service_state),
    ) -> RuntimeResponse:
        config = state.config
        return RuntimeResponse(
            service=RuntimeServiceView(
                listen_address=config.service.listen_address,
                port=config.service.port,
                public_url=config.service.public_url,
                host_name=config.service.host_name,
                base_url=config.service.base_url(),
            ),
            paths=config.paths.as_json(),
            dependencies=RuntimeDependencyView(
                erpnext_url=config.dependencies.erpnext_url,
                ollama_url=config.dependencies.ollama_url,
                docling_url=config.dependencies.docling_url,
                n8n_url=config.dependencies.n8n_url,
                erpnext_credentials_file_present=(
                    config.dependencies.erpnext_credentials_file is not None
                ),
            ),
        )

    @app.post(
        "/api/tools/run",
        response_model=ToolResponse,
        tags=["tools"],
        responses={
            400: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    async def run_tool(
        payload: ToolRunRequest,
        background_tasks: BackgroundTasks,
        state: ServiceState = Depends(get_service_state),
        operator_id: str | None = Header(default=None, alias="X-Operator-Id"),
    ) -> ToolResponse:
        _ = background_tasks
        return state.execute(payload, operator_id=operator_id)

    return app


def get_service_state(request: Request) -> ServiceState:
    return request.app.state.service_state


def serve_http(config: RuntimeConfig | None = None) -> None:
    runtime_config = config or RuntimeConfig.from_env()
    uvicorn.run(
        create_app(runtime_config),
        host=runtime_config.service.listen_address,
        port=runtime_config.service.port,
        log_level="info",
    )
