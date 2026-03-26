from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from ..modeling import InvoiceAIModel


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class QuoteLineIntent(InvoiceAIModel):
    item_code: str | None = None
    item_name: str | None = None
    description: str
    qty: float
    rate: float | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QuoteLineIntent":
        return cls(
            item_code=_optional_string(payload.get("item_code")),
            item_name=_optional_string(payload.get("item_name")),
            description=str(payload.get("description", "")),
            qty=float(payload.get("qty", 0)),
            rate=None if payload.get("rate") is None else float(payload["rate"]),
        )

    @model_validator(mode="after")
    def _validate_description(self) -> "QuoteLineIntent":
        if not self.description.strip():
            raise ValueError("Quote line requires description")
        return self

    def lookup_label(self) -> str:
        return self.item_code or self.item_name or self.description


class QuoteDraftRequest(InvoiceAIModel):
    request_id: str
    draft_key: str
    customer: str | None = None
    customer_name: str | None = None
    company: str
    currency: str = "AUD"
    narrative: dict[str, str] = Field(default_factory=dict)
    line_items: tuple[QuoteLineIntent, ...]
    source_refs: tuple[dict[str, Any], ...] = Field(default_factory=tuple)

    @classmethod
    def from_payload(cls, request_id: str, payload: dict[str, Any]) -> "QuoteDraftRequest":
        customer = payload.get("customer")
        customer_block = customer if isinstance(customer, dict) else {}
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
                "intro": str(dict(payload.get("narrative", {})).get("intro") or "Quote Draft"),
                "notes": str(dict(payload.get("narrative", {})).get("notes") or ""),
            },
            line_items=tuple(
                QuoteLineIntent.from_dict(item)
                for item in payload.get("line_items", payload.get("items", []))
            ),
            source_refs=tuple(dict(ref) for ref in payload.get("source_refs", [])),
        )

    @model_validator(mode="after")
    def _validate_items(self) -> "QuoteDraftRequest":
        if not self.line_items:
            raise ValueError("Quote draft requires at least one line item")
        return self


class QuoteRevisionRequest(InvoiceAIModel):
    request_id: str
    draft_key: str
    quotation: str | None = None
    patch: dict[str, Any] = Field(default_factory=dict)
    summary: str

    @classmethod
    def from_payload(cls, request_id: str, payload: dict[str, Any]) -> "QuoteRevisionRequest":
        return cls(
            request_id=request_id,
            draft_key=str(payload["draft_key"]),
            quotation=_optional_string(payload.get("quotation")),
            patch=dict(payload.get("patch", {})),
            summary=str(payload.get("summary") or "Quote draft revised"),
        )
