from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from .erp.schemas import ToolResponse
from .modeling import InvoiceAIModel


class IngestProcessedRecord(InvoiceAIModel):
    request_id: str
    source: dict[str, Any] = Field(default_factory=dict)
    proposal: dict[str, Any] = Field(default_factory=dict)


class IngestSourceRecord(InvoiceAIModel):
    request_id: str
    source: dict[str, Any] = Field(default_factory=dict)


class IngestExtractedRecord(InvoiceAIModel):
    request_id: str
    source: dict[str, Any] = Field(default_factory=dict)
    extracted: dict[str, Any] = Field(default_factory=dict)


class IngestRejectedRecord(InvoiceAIModel):
    request_id: str
    source: dict[str, Any] = Field(default_factory=dict)
    error_summary: dict[str, Any] = Field(default_factory=dict)


class IngestComposedResultRecord(InvoiceAIModel):
    request_id: str
    result: ToolResponse


class QuotationRevisionRecord(InvoiceAIModel):
    revision_id: str
    revision_number: int
    draft_key: str
    quotation: str | None = None
    revision_type: str
    summary: str
    created_at: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    quotation_doc: dict[str, Any] = Field(default_factory=dict)
    preview_path: str | None = None


class LatestQuotationRevisionRecord(InvoiceAIModel):
    draft_key: str
    quotation: str | None = None
    latest_revision_id: str
    latest_revision_number: int
    updated_at: str
    latest_revision_path: str
    preview_path: str | None = None

    def revision_path(self) -> Path:
        return Path(self.latest_revision_path)


class SalesInvoiceRevisionRecord(InvoiceAIModel):
    revision_id: str
    revision_number: int
    draft_key: str
    sales_invoice: str | None = None
    source_quotation: str | None = None
    revision_type: str
    summary: str
    created_at: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    sales_invoice_doc: dict[str, Any] = Field(default_factory=dict)
    preview_path: str | None = None


class LatestSalesInvoiceRevisionRecord(InvoiceAIModel):
    draft_key: str
    sales_invoice: str | None = None
    source_quotation: str | None = None
    latest_revision_id: str
    latest_revision_number: int
    updated_at: str
    latest_revision_path: str
    preview_path: str | None = None

    def revision_path(self) -> Path:
        return Path(self.latest_revision_path)
