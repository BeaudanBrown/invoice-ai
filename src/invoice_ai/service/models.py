from __future__ import annotations

from typing import Any

from pydantic import Field

from ..control_plane.models import (
    ArtifactRecord,
    JobEventRecord,
    JobRecord,
    RequestRecord,
    ReviewActionRecord,
    ReviewRecord,
)
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
    operator_auth_configured: bool


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


class OperatorView(InvoiceAIModel):
    operator_id: str


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


class RequestListResponse(InvoiceAIModel):
    requests: tuple[RequestRecord, ...] = Field(default_factory=tuple)


class RequestDetailResponse(InvoiceAIModel):
    request: RequestRecord
    job: JobRecord | None = None
    artifacts: tuple[ArtifactRecord, ...] = Field(default_factory=tuple)


class JobListResponse(InvoiceAIModel):
    jobs: tuple[JobRecord, ...] = Field(default_factory=tuple)


class JobDetailResponse(InvoiceAIModel):
    job: JobRecord
    events: tuple[JobEventRecord, ...] = Field(default_factory=tuple)


class ReviewListResponse(InvoiceAIModel):
    reviews: tuple[ReviewRecord, ...] = Field(default_factory=tuple)


class ReviewDetailResponse(InvoiceAIModel):
    review: ReviewRecord
    actions: tuple[ReviewActionRecord, ...] = Field(default_factory=tuple)
    artifacts: tuple[ArtifactRecord, ...] = Field(default_factory=tuple)


class UITurnRequest(InvoiceAIModel):
    request_id: str | None = None
    message: str
    defaults: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    conversation_context: dict[str, Any] = Field(default_factory=dict)
    write_approval_artifacts: bool = True


class UIArtifactView(InvoiceAIModel):
    kind: str
    label: str
    file_name: str
    content_type: str | None = None
    url: str | None = None
    download_url: str | None = None
    available: bool = False


class UIReviewView(InvoiceAIModel):
    review_id: str
    kind: str
    status: str
    summary: str
    actions: tuple[str, ...] = Field(default_factory=tuple)
    artifacts: tuple[UIArtifactView, ...] = Field(default_factory=tuple)


class UISummaryView(InvoiceAIModel):
    text: str
    stage: str
    status: str


class UITurnResponse(InvoiceAIModel):
    request_id: str
    status: str
    stage: str
    summary: UISummaryView
    conversation_state: dict[str, Any] = Field(default_factory=dict)
    artifacts: tuple[UIArtifactView, ...] = Field(default_factory=tuple)
    current_artifact: UIArtifactView | None = None
    reviews: tuple[UIReviewView, ...] = Field(default_factory=tuple)
    erp_refs: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    errors: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
