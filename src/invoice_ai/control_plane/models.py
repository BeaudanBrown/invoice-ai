from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from ..modeling import InvoiceAIModel


class RequestSource(StrEnum):
    CLI = "cli"
    HTTP = "http"
    INTERNAL = "internal"


class RequestLifecycleStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    APPROVAL_REQUIRED = "approval_required"
    VALIDATION_ERROR = "validation_error"
    BLOCKED = "blocked"
    NOT_FOUND = "not_found"
    INTERNAL_ERROR = "internal_error"


class JobStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    APPROVAL_REQUIRED = "approval_required"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RequestRecord(InvoiceAIModel):
    request_id: str
    source: RequestSource
    tool_name: str
    operator_id: str | None = None
    dry_run: bool = False
    request_body_hash: str
    request_body: dict[str, Any] = Field(default_factory=dict)
    status: RequestLifecycleStatus
    created_at: str
    finished_at: str | None = None
    response_body_hash: str | None = None
    error_count: int = 0
    warning_count: int = 0


class JobRecord(InvoiceAIModel):
    job_id: str
    request_id: str
    job_kind: str
    status: JobStatus
    started_at: str
    finished_at: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class JobEventRecord(InvoiceAIModel):
    event_id: str
    job_id: str
    request_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class IdempotencyKeyRecord(InvoiceAIModel):
    key: str
    scope: str
    request_id: str
    result_fingerprint: str
    created_at: str
    retention_marker: str | None = None


class ReviewRecord(InvoiceAIModel):
    review_id: str
    request_id: str | None = None
    review_kind: str
    status: ReviewStatus
    target: dict[str, Any] = Field(default_factory=dict)
    target_summary: str | None = None
    artifact_dir: str | None = None
    created_at: str
    updated_at: str


class ReviewActionRecord(InvoiceAIModel):
    action_id: str
    review_id: str
    action_type: str
    operator_id: str | None = None
    note: str | None = None
    created_at: str


class ArtifactRecord(InvoiceAIModel):
    artifact_id: str
    parent_kind: str
    parent_id: str
    request_id: str | None = None
    artifact_kind: str
    path: str
    content_hash: str | None = None
    created_at: str


class IngestIndexRecord(InvoiceAIModel):
    ingest_id: str
    request_id: str
    source_fingerprint: str | None = None
    supplier_hint: str | None = None
    external_invoice_reference: str | None = None
    linked_review_id: str | None = None
    linked_erp_doctype: str | None = None
    linked_erp_name: str | None = None
    record_dir: str | None = None
    updated_at: str


class MemorySuggestionIndexRecord(InvoiceAIModel):
    suggestion_id: str
    scope: str
    slug: str
    status: ReviewStatus
    linked_review_id: str | None = None
    current_document_path: str | None = None
    updated_at: str
