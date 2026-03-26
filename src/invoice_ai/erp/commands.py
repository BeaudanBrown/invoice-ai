from __future__ import annotations

from typing import Any

from pydantic import Field

from ..modeling import InvoiceAIModel


class ERPDocumentRef(InvoiceAIModel):
    doctype: str
    name: str | None = None


class GetDocCommand(InvoiceAIModel):
    doctype: str
    name: str
    fields: list[str] = Field(default_factory=list)


class ListDocsCommand(InvoiceAIModel):
    doctype: str
    filters: dict[str, Any] | None = None
    fields: list[str] = Field(default_factory=list)
    order_by: str | None = None
    limit: int = 20


class LinkedContextCommand(InvoiceAIModel):
    subject: ERPDocumentRef
    include: list[str] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    limit_per_relation: int = 10


class PricingContextCommand(InvoiceAIModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    customer: str | None = None
    supplier: str | None = None


class CreateDraftQuotationCommand(InvoiceAIModel):
    customer: str
    company: str
    currency: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    narrative: dict[str, str] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class UpdateDraftQuotationCommand(InvoiceAIModel):
    quotation: str
    patch: dict[str, Any] = Field(default_factory=dict)


class CreateDraftSalesInvoiceCommand(InvoiceAIModel):
    customer: str | None = None
    company: str
    currency: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    narrative: dict[str, str] = Field(default_factory=dict)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    quotation: str | None = None


class UpdateDraftSalesInvoiceCommand(InvoiceAIModel):
    sales_invoice: str
    patch: dict[str, Any] = Field(default_factory=dict)


class CreateDraftPurchaseInvoiceCommand(InvoiceAIModel):
    supplier: str | None = None
    bill_no: str | None = None
    posting_date: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)


class AttachFileCommand(InvoiceAIModel):
    target: ERPDocumentRef
    source_path: str
    file_name: str | None = None
    is_private: bool = True
