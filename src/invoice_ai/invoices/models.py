from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from ..modeling import InvoiceAIModel


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class InvoiceLineIntent(InvoiceAIModel):
    item_code: str | None = None
    item_name: str | None = None
    description: str
    qty: float
    rate: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "InvoiceLineIntent":
        return cls(
            item_code=_optional_string(payload.get("item_code")),
            item_name=_optional_string(payload.get("item_name")),
            description=str(payload.get("description", "")),
            qty=float(payload.get("qty", 0)),
            rate=None if payload.get("rate") is None else float(payload["rate"]),
        )

    @model_validator(mode="after")
    def _validate_description(self) -> "InvoiceLineIntent":
        if not self.description.strip():
            raise ValueError("Sales invoice line requires description")
        return self

    def lookup_label(self) -> str:
        return self.item_code or self.item_name or self.description


class InvoiceDraftRequest(InvoiceAIModel):
    request_id: str
    draft_key: str
    customer: str | None = None
    customer_name: str | None = None
    company: str
    currency: str = "AUD"
    narrative: dict[str, str] = Field(default_factory=dict)
    line_items: tuple[InvoiceLineIntent, ...] = Field(default_factory=tuple)
    source_refs: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    quotation: str | None = None

    @classmethod
    def from_payload(cls, request_id: str, payload: dict[str, Any]) -> "InvoiceDraftRequest":
        customer = payload.get("customer")
        customer_block = customer if isinstance(customer, dict) else {}
        narrative = dict(payload.get("narrative", {}))
        return cls(
            request_id=request_id,
            draft_key=str(payload.get("draft_key") or request_id),
            customer=_optional_string(payload.get("customer"))
            or _optional_string(customer_block.get("id"))
            or _optional_string(customer_block.get("name")),
            customer_name=_optional_string(payload.get("customer_name"))
            or _optional_string(customer_block.get("display_name")),
            company=str(payload["company"]),
            currency=str(payload.get("currency", "AUD")),
            narrative={
                "intro": str(
                    narrative.get("intro")
                    or ("Sales Invoice Draft" if payload.get("quotation") is None else "Sales Invoice Draft from Quote")
                ),
                "notes": str(narrative.get("notes") or ""),
            },
            line_items=tuple(
                InvoiceLineIntent.from_dict(item)
                for item in payload.get("line_items", payload.get("items", []))
            ),
            source_refs=tuple(dict(ref) for ref in payload.get("source_refs", [])),
            quotation=_optional_string(payload.get("quotation")),
        )

    @model_validator(mode="after")
    def _validate_shape(self) -> "InvoiceDraftRequest":
        if self.quotation is None and not self.line_items:
            raise ValueError(
                "Sales invoice draft requires either quotation or at least one line item"
            )
        return self


class InvoiceRevisionRequest(InvoiceAIModel):
    request_id: str
    draft_key: str
    sales_invoice: str | None = None
    patch: dict[str, Any] = Field(default_factory=dict)
    summary: str

    @classmethod
    def from_payload(cls, request_id: str, payload: dict[str, Any]) -> "InvoiceRevisionRequest":
        return cls(
            request_id=request_id,
            draft_key=str(payload["draft_key"]),
            sales_invoice=_optional_string(payload.get("sales_invoice")),
            patch=dict(payload.get("patch", {})),
            summary=str(payload.get("summary") or "Sales invoice draft revised"),
        )
