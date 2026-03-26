from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
import uvicorn

from ..config import RuntimeConfig
from ..control_plane.models import JobStatus, RequestLifecycleStatus, ReviewStatus
from ..control_plane.models import RequestSource
from ..control_plane.store import ControlPlaneStore
from ..erp.schemas import ToolResponse
from ..execution import execute_tool_request
from .auth import OperatorAuthenticator
from .models import (
    ErrorResponse,
    HealthResponse,
    JobDetailResponse,
    JobListResponse,
    OperatorView,
    RequestDetailResponse,
    RequestListResponse,
    ReviewDetailResponse,
    ReviewListResponse,
    RuntimeDependencyView,
    RuntimeResponse,
    RuntimeServiceView,
    ToolRunRequest,
)


@dataclass(frozen=True)
class ServiceState:
    config: RuntimeConfig
    control_plane: ControlPlaneStore
    authenticator: OperatorAuthenticator

    def execute(
        self,
        payload: ToolRunRequest,
        *,
        operator_id: str,
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
        authenticator=OperatorAuthenticator(
            tokens_file=runtime_config.service.operator_tokens_file
        ),
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

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        error = "http_error"
        if exc.status_code == 401:
            error = "unauthorized"
        elif exc.status_code == 404:
            error = "not_found"
        elif exc.status_code == 503:
            error = "service_unavailable"
        payload = ErrorResponse(error=error, message=str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=payload.as_dict())

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
        _operator: OperatorView = Depends(require_operator),
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
                operator_auth_configured=state.authenticator.is_configured(),
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
            401: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            400: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )
    async def run_tool(
        payload: ToolRunRequest,
        operator: OperatorView = Depends(require_operator),
        state: ServiceState = Depends(get_service_state),
    ) -> ToolResponse:
        return state.execute(payload, operator_id=operator.operator_id)

    @app.get(
        "/api/requests",
        response_model=RequestListResponse,
        tags=["operator"],
        responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    async def list_requests(
        _operator: OperatorView = Depends(require_operator),
        state: ServiceState = Depends(get_service_state),
        limit: int = Query(default=50, ge=1, le=200),
        status_value: str | None = Query(default=None, alias="status"),
        tool_name: str | None = Query(default=None),
        operator_id: str | None = Query(default=None),
    ) -> RequestListResponse:
        request_status = (
            None
            if status_value is None
            else RequestLifecycleStatus(status_value)
        )
        return RequestListResponse(
            requests=state.control_plane.list_requests(
                limit=limit,
                status=request_status,
                tool_name=tool_name,
                operator_id=operator_id,
            )
        )

    @app.get(
        "/api/requests/{request_id}",
        response_model=RequestDetailResponse,
        tags=["operator"],
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    async def get_request(
        request_id: str,
        _operator: OperatorView = Depends(require_operator),
        state: ServiceState = Depends(get_service_state),
    ) -> RequestDetailResponse:
        request_record = state.control_plane.get_request(request_id=request_id)
        if request_record is None:
            raise HTTPException(status_code=404, detail=f"Request not found: {request_id}")
        return RequestDetailResponse(
            request=request_record,
            job=state.control_plane.get_job(job_id=request_id),
            artifacts=state.control_plane.list_artifacts(request_id=request_id),
        )

    @app.get(
        "/api/jobs",
        response_model=JobListResponse,
        tags=["operator"],
        responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    async def list_jobs(
        _operator: OperatorView = Depends(require_operator),
        state: ServiceState = Depends(get_service_state),
        limit: int = Query(default=50, ge=1, le=200),
        status_value: str | None = Query(default=None, alias="status"),
        job_kind: str | None = Query(default=None),
        request_id: str | None = Query(default=None),
    ) -> JobListResponse:
        job_status = None if status_value is None else JobStatus(status_value)
        return JobListResponse(
            jobs=state.control_plane.list_jobs(
                limit=limit,
                status=job_status,
                job_kind=job_kind,
                request_id=request_id,
            )
        )

    @app.get(
        "/api/jobs/{job_id}",
        response_model=JobDetailResponse,
        tags=["operator"],
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    async def get_job(
        job_id: str,
        _operator: OperatorView = Depends(require_operator),
        state: ServiceState = Depends(get_service_state),
        event_limit: int = Query(default=200, ge=1, le=1000),
    ) -> JobDetailResponse:
        job_record = state.control_plane.get_job(job_id=job_id)
        if job_record is None:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
        return JobDetailResponse(
            job=job_record,
            events=state.control_plane.list_job_events(job_id=job_id, limit=event_limit),
        )

    @app.get(
        "/api/reviews",
        response_model=ReviewListResponse,
        tags=["operator"],
        responses={401: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )
    async def list_reviews(
        _operator: OperatorView = Depends(require_operator),
        state: ServiceState = Depends(get_service_state),
        limit: int = Query(default=50, ge=1, le=200),
        status_value: str | None = Query(default=None, alias="status"),
        review_kind: str | None = Query(default=None),
    ) -> ReviewListResponse:
        review_status = None if status_value is None else ReviewStatus(status_value)
        return ReviewListResponse(
            reviews=state.control_plane.list_reviews(
                limit=limit,
                status=review_status,
                review_kind=review_kind,
            )
        )

    @app.get(
        "/api/reviews/{review_id}",
        response_model=ReviewDetailResponse,
        tags=["operator"],
        responses={
            401: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    async def get_review(
        review_id: str,
        _operator: OperatorView = Depends(require_operator),
        state: ServiceState = Depends(get_service_state),
    ) -> ReviewDetailResponse:
        review_record = state.control_plane.get_review(review_id=review_id)
        if review_record is None:
            raise HTTPException(status_code=404, detail=f"Review not found: {review_id}")
        return ReviewDetailResponse(
            review=review_record,
            actions=state.control_plane.list_review_actions(review_id=review_id),
            artifacts=state.control_plane.list_artifacts(
                parent_kind="review",
                parent_id=review_id,
            ),
        )

    return app


def get_service_state(request: Request) -> ServiceState:
    return request.app.state.service_state


def require_operator(
    authorization: str | None = Header(default=None, alias="Authorization"),
    state: ServiceState = Depends(get_service_state),
) -> OperatorView:
    if not state.authenticator.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operator authentication is not configured",
        )
    token = _bearer_token(authorization)
    identity = state.authenticator.authenticate_bearer_token(token)
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid operator bearer token required",
        )
    return OperatorView(operator_id=identity.operator_id)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def serve_http(config: RuntimeConfig | None = None) -> None:
    runtime_config = config or RuntimeConfig.from_env()
    uvicorn.run(
        create_app(runtime_config),
        host=runtime_config.service.listen_address,
        port=runtime_config.service.port,
        log_level="info",
    )
