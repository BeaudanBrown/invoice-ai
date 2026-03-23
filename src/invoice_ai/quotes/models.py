from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class QuoteLineIntent:
    item_code: str | None
    item_name: str | None
    description: str
    qty: float
    rate: float | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QuoteLineIntent":
        rate = payload.get("rate")
        return cls(
            item_code=_optional_string(payload.get("item_code")),
            item_name=_optional_string(payload.get("item_name")),
            description=str(payload.get("description", "")),
            qty=float(payload.get("qty", 0)),
            rate=None if rate is None else float(rate),
        )

    def lookup_label(self) -> str:
        return self.item_code or self.item_name or self.description

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_code": self.item_code,
            "item_name": self.item_name,
            "description": self.description,
            "qty": self.qty,
            "rate": self.rate,
        }


@dataclass(frozen=True)
class QuoteDraftRequest:
    request_id: str
    draft_key: str
    customer: str | None
    customer_name: str | None
    company: str
    currency: str
    narrative: dict[str, str]
    line_items: tuple[QuoteLineIntent, ...]
    source_refs: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def from_payload(cls, request_id: str, payload: dict[str, Any]) -> "QuoteDraftRequest":
        customer = payload.get("customer")
        customer_block = customer if isinstance(customer, dict) else {}
        draft_key = str(payload.get("draft_key") or request_id)
        line_items = tuple(
            QuoteLineIntent.from_dict(item)
            for item in payload.get("line_items", payload.get("items", []))
        )
        return cls(
            request_id=request_id,
            draft_key=draft_key,
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
            line_items=line_items,
            source_refs=tuple(dict(ref) for ref in payload.get("source_refs", [])),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "draft_key": self.draft_key,
            "customer": self.customer,
            "customer_name": self.customer_name,
            "company": self.company,
            "currency": self.currency,
            "narrative": self.narrative,
            "line_items": [item.as_dict() for item in self.line_items],
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class QuoteRevisionRequest:
    request_id: str
    draft_key: str
    quotation: str | None
    patch: dict[str, Any]
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

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "draft_key": self.draft_key,
            "quotation": self.quotation,
            "patch": self.patch,
            "summary": self.summary,
        }
