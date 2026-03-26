from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from ..modeling import InvoiceAIModel


def _looks_like_supplier_document(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in ("supplier_document", "document_path", "raw_text", "source_path", "file_name")
    )


def _looks_like_quote_request(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in ("quote", "customer", "customer_name", "line_items", "items", "draft_key")
    )


def _looks_like_quote_revision(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("quote_revision", "patch", "quotation", "active_quote"))


def _looks_like_invoice_request(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in (
            "invoice",
            "sales_invoice",
            "invoice_from_quote",
            "invoice_draft",
        )
    )


def _looks_like_invoice_revision(payload: dict[str, Any]) -> bool:
    return any(
        key in payload for key in ("invoice_revision", "sales_invoice", "active_invoice")
    )


def _looks_like_review_queue_request(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in ("review_queue", "review_status", "review_scope")
    )


class OperatorRequestKind(StrEnum):
    SUPPLIER_DOCUMENT_INTAKE = "supplier_document_intake"
    REVIEW_QUEUE = "review_queue"
    QUOTE_DRAFT = "quote_draft"
    QUOTE_REVISION = "quote_revision"
    INVOICE_DRAFT = "invoice_draft"
    INVOICE_REVISION = "invoice_revision"


class OperatorRequest(InvoiceAIModel):
    request_id: str
    request_kind: OperatorRequestKind
    operator_message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    conversation_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        request_id: str,
        payload: dict[str, Any],
        *,
        conversation_context: dict[str, Any] | None = None,
    ) -> "OperatorRequest":
        request_kind = str(payload.get("request_kind") or payload.get("kind") or "").strip()
        if not request_kind:
            if _looks_like_supplier_document(payload):
                request_kind = OperatorRequestKind.SUPPLIER_DOCUMENT_INTAKE
            elif _looks_like_review_queue_request(payload):
                request_kind = OperatorRequestKind.REVIEW_QUEUE
            elif _looks_like_invoice_revision(payload):
                request_kind = OperatorRequestKind.INVOICE_REVISION
            elif _looks_like_invoice_request(payload):
                request_kind = OperatorRequestKind.INVOICE_DRAFT
            elif _looks_like_quote_revision(payload):
                request_kind = OperatorRequestKind.QUOTE_REVISION
            elif _looks_like_quote_request(payload):
                request_kind = OperatorRequestKind.QUOTE_DRAFT
            else:
                raise ValueError(
                    "Could not infer orchestrator request kind; provide request_kind explicitly"
                )

        normalized_kind = str(request_kind).replace("-", "_")
        return cls(
            request_id=request_id,
            request_kind=OperatorRequestKind(normalized_kind),
            operator_message=_optional_string(payload.get("operator_message"))
            or _optional_string(payload.get("message")),
            payload=dict(payload),
            conversation_context=dict(conversation_context or {}),
        )

    def delegated_tool_name(self) -> str:
        if self.request_kind == OperatorRequestKind.SUPPLIER_DOCUMENT_INTAKE:
            return "ingest.process_supplier_document"
        if self.request_kind == OperatorRequestKind.REVIEW_QUEUE:
            return "memory.list_reviews"
        if self.request_kind == OperatorRequestKind.INVOICE_REVISION:
            return "invoices.revise_draft"
        if self.request_kind == OperatorRequestKind.INVOICE_DRAFT:
            return "invoices.create_draft"
        if self.request_kind == OperatorRequestKind.QUOTE_REVISION:
            return "quotes.revise_draft"
        return "quotes.create_draft"

    def delegated_payload(self) -> dict[str, Any]:
        if self.request_kind == OperatorRequestKind.SUPPLIER_DOCUMENT_INTAKE:
            nested = self.payload.get("supplier_document")
            if isinstance(nested, dict):
                return dict(nested)
            return _clean_payload(self.payload)

        if self.request_kind == OperatorRequestKind.REVIEW_QUEUE:
            nested = self.payload.get("review_queue")
            if isinstance(nested, dict):
                payload = dict(nested)
            else:
                payload = _clean_payload(self.payload)
            if "review_status" in payload and "status" not in payload:
                payload["status"] = payload.pop("review_status")
            if "review_scope" in payload and "scope" not in payload:
                payload["scope"] = payload.pop("review_scope")
            return payload

        if self.request_kind == OperatorRequestKind.QUOTE_REVISION:
            nested = self.payload.get("quote_revision")
            if isinstance(nested, dict):
                payload = dict(nested)
            else:
                payload = _clean_payload(self.payload)

            active_quote = self.active_quote_context()
            if "draft_key" not in payload and active_quote.get("draft_key") is not None:
                payload["draft_key"] = active_quote["draft_key"]
            if "quotation" not in payload and active_quote.get("quotation") is not None:
                payload["quotation"] = active_quote["quotation"]
            if "draft_key" not in payload:
                raise ValueError(
                    "quote_revision requires draft_key or conversation_context.active_quote.draft_key"
                )
            return payload

        if self.request_kind == OperatorRequestKind.INVOICE_REVISION:
            nested = self.payload.get("invoice_revision")
            if isinstance(nested, dict):
                payload = dict(nested)
            else:
                payload = _clean_payload(self.payload)

            active_invoice = self.active_invoice_context()
            if "draft_key" not in payload and active_invoice.get("draft_key") is not None:
                payload["draft_key"] = active_invoice["draft_key"]
            if (
                "sales_invoice" not in payload
                and active_invoice.get("sales_invoice") is not None
            ):
                payload["sales_invoice"] = active_invoice["sales_invoice"]
            if "draft_key" not in payload:
                raise ValueError(
                    "invoice_revision requires draft_key or conversation_context.active_invoice.draft_key"
                )
            return payload

        if self.request_kind == OperatorRequestKind.INVOICE_DRAFT:
            nested = self.payload.get("invoice")
            if not isinstance(nested, dict):
                nested = self.payload.get("invoice_draft")
            if not isinstance(nested, dict):
                nested = self.payload.get("invoice_from_quote")
            if isinstance(nested, dict):
                payload = dict(nested)
            else:
                payload = _clean_payload(self.payload)
            if "draft_key" not in payload:
                payload["draft_key"] = self.request_id
            return payload

        nested = self.payload.get("quote")
        if isinstance(nested, dict):
            payload = dict(nested)
        else:
            payload = _clean_payload(self.payload)
        if "draft_key" not in payload:
            payload["draft_key"] = self.request_id
        return payload

    def active_quote_context(self) -> dict[str, Any]:
        active_quote = self.payload.get("active_quote")
        if isinstance(active_quote, dict):
            return dict(active_quote)
        from_context = self.conversation_context.get("active_quote")
        if isinstance(from_context, dict):
            return dict(from_context)
        return {}

    def active_invoice_context(self) -> dict[str, Any]:
        active_invoice = self.payload.get("active_invoice")
        if isinstance(active_invoice, dict):
            return dict(active_invoice)
        from_context = self.conversation_context.get("active_invoice")
        if isinstance(from_context, dict):
            return dict(from_context)
        return {}


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(payload)
    cleaned.pop("request_kind", None)
    cleaned.pop("kind", None)
    cleaned.pop("operator_message", None)
    cleaned.pop("message", None)
    return cleaned


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
