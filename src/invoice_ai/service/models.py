from __future__ import annotations

from typing import Any

from pydantic import Field

from ..erp.schemas import ToolResponse
from ..modeling import InvoiceAIModel


class HealthResponse(InvoiceAIModel):
    status: str
    service: str
    listen_address: str
    port: int


class RuntimeServiceView(InvoiceAIModel):
    listen_address: str
    port: int
    public_url: str | None = None
    host_name: str | None = None
    base_url: str


class RuntimeDependencyView(InvoiceAIModel):
    erpnext_url: str | None = None
    ollama_url: str
    docling_url: str | None = None
    n8n_url: str | None = None
    erpnext_credentials_file_present: bool


class RuntimeResponse(InvoiceAIModel):
    service: RuntimeServiceView
    paths: dict[str, Any] = Field(default_factory=dict)
    dependencies: RuntimeDependencyView


class ToolRunRequest(InvoiceAIModel):
    request_id: str
    tool_name: str
    dry_run: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    conversation_context: dict[str, Any] = Field(default_factory=dict)
    write_approval_artifacts: bool = False

    def tool_request(self):
        from ..erp.schemas import ToolRequest

        return ToolRequest(
            request_id=self.request_id,
            tool_name=self.tool_name,
            dry_run=self.dry_run,
            payload=self.payload,
            conversation_context=self.conversation_context,
        )


class ErrorResponse(InvoiceAIModel):
    error: str
    message: str


class ToolRunResponse(InvoiceAIModel):
    response: ToolResponse
