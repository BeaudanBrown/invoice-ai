from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any

from ..approvals.store import ApprovalStore
from ..config import RuntimeConfig
from ..erp.schemas import ToolRequest
from ..erp.tools import ERPToolExecutor
from ..ingest.tools import IngestToolExecutor
from ..quotes.tools import QuoteToolExecutor


@dataclass(frozen=True)
class ToolExecutionContext:
    config: RuntimeConfig

    def execute(
        self,
        payload: dict[str, Any],
        *,
        write_approval_artifacts: bool,
    ) -> dict[str, Any]:
        request = ToolRequest.from_dict(payload)
        response = _tool_executor_for(request.tool_name, self.config).execute(request)
        if write_approval_artifacts and response.approval is not None:
            ApprovalStore(self.config.paths.approvals_dir).write(response)
        return response.as_dict()


class InvoiceAIHTTPServer(ThreadingHTTPServer):
    def __init__(self, config: RuntimeConfig) -> None:
        self.runtime_config = config
        self.tool_context = ToolExecutionContext(config)
        address = (config.service.listen_address, config.service.port)
        super().__init__(address, InvoiceAIRequestHandler)


class InvoiceAIRequestHandler(BaseHTTPRequestHandler):
    server: InvoiceAIHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self._json_response(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "invoice-ai",
                    "listen_address": self.server.runtime_config.service.listen_address,
                    "port": self.server.runtime_config.service.port,
                },
            )
            return

        if self.path == "/api/runtime":
            config = self.server.runtime_config
            self._json_response(
                HTTPStatus.OK,
                {
                    "service": {
                        "listen_address": config.service.listen_address,
                        "port": config.service.port,
                        "public_url": config.service.public_url,
                        "host_name": config.service.host_name,
                        "base_url": config.service.base_url(),
                    },
                    "paths": config.paths.as_json(),
                    "dependencies": {
                        "erpnext_url": config.dependencies.erpnext_url,
                        "ollama_url": config.dependencies.ollama_url,
                        "docling_url": config.dependencies.docling_url,
                        "n8n_url": config.dependencies.n8n_url,
                        "erpnext_credentials_file_present": (
                            config.dependencies.erpnext_credentials_file is not None
                        ),
                    },
                },
            )
            return

        self._json_response(
            HTTPStatus.NOT_FOUND,
            {"error": "not_found", "message": f"Unhandled path: {self.path}"},
        )

    def do_POST(self) -> None:
        if self.path != "/api/tools/run":
            self._json_response(
                HTTPStatus.NOT_FOUND,
                {"error": "not_found", "message": f"Unhandled path: {self.path}"},
            )
            return

        try:
            payload = self._read_json_body()
            write_approval_artifacts = bool(
                payload.pop("write_approval_artifacts", False)
            )
            result = self.server.tool_context.execute(
                payload,
                write_approval_artifacts=write_approval_artifacts,
            )
        except ValueError as exc:
            self._json_response(
                HTTPStatus.BAD_REQUEST,
                {"error": "bad_request", "message": str(exc)},
            )
            return
        except Exception as exc:  # pragma: no cover - defensive server seam
            self._json_response(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "internal_error", "message": str(exc)},
            )
            return

        self._json_response(HTTPStatus.OK, result)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Request body is required")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def _json_response(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _tool_executor_for(tool_name: str, config: RuntimeConfig) -> object:
    if tool_name.startswith("erp."):
        return ERPToolExecutor.from_runtime_config(config)
    if tool_name.startswith("ingest."):
        return IngestToolExecutor.from_runtime_config(config)
    if tool_name.startswith("quotes."):
        return QuoteToolExecutor.from_runtime_config(config)
    raise ValueError(f"Unsupported tool family for {tool_name}")
