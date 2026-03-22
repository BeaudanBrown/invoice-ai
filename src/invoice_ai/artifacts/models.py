from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QuoteLineItem:
    item_code: str
    qty: float
    rate: float
    description: str

    @property
    def amount(self) -> float:
        return self.qty * self.rate


@dataclass(frozen=True)
class QuotePreview:
    draft_key: str
    customer: str
    company: str
    currency: str
    title: str
    notes: str
    items: tuple[QuoteLineItem, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QuotePreview":
        narrative = dict(payload.get("narrative", {}))
        items = tuple(
            QuoteLineItem(
                item_code=str(item.get("item_code", "")),
                qty=float(item.get("qty", 0)),
                rate=float(item.get("rate", 0)),
                description=str(item.get("description", "")),
            )
            for item in payload.get("items", [])
        )
        return cls(
            draft_key=str(payload["draft_key"]),
            customer=str(payload["customer"]),
            company=str(payload["company"]),
            currency=str(payload.get("currency", "AUD")),
            title=str(narrative.get("intro") or "Quote Preview"),
            notes=str(narrative.get("notes") or ""),
            items=items,
        )

    @property
    def total(self) -> float:
        return sum(item.amount for item in self.items)
