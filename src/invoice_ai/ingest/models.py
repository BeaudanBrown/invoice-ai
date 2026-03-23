from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SupplierCandidate:
    supplier_name: str
    supplier_id: str | None = None
    confidence: float = 0.0
    matched: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "supplier_name": self.supplier_name,
            "supplier_id": self.supplier_id,
            "confidence": self.confidence,
            "matched": self.matched,
        }


@dataclass(frozen=True)
class ItemCandidate:
    source_label: str
    item_code: str | None = None
    confidence: float = 0.0
    matched: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_label": self.source_label,
            "item_code": self.item_code,
            "confidence": self.confidence,
            "matched": self.matched,
        }


@dataclass(frozen=True)
class SupplierInvoiceLine:
    description: str
    qty: float
    rate: float
    amount: float | None = None
    item_code: str | None = None
    item_name: str | None = None
    candidate: ItemCandidate | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SupplierInvoiceLine":
        qty = float(payload.get("qty", 0))
        rate = float(payload.get("rate", 0))
        amount = payload.get("amount")
        return cls(
            description=str(payload.get("description", "")),
            qty=qty,
            rate=rate,
            amount=None if amount is None else float(amount),
            item_code=_optional_string(payload.get("item_code")),
            item_name=_optional_string(payload.get("item_name")),
        )

    def normalized_amount(self) -> float:
        if self.amount is not None:
            return self.amount
        return round(self.qty * self.rate, 2)

    def lookup_label(self) -> str:
        return self.item_code or self.item_name or self.description

    def as_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "qty": self.qty,
            "rate": self.rate,
            "amount": self.normalized_amount(),
            "item_code": self.item_code,
            "item_name": self.item_name,
            "candidate": None if self.candidate is None else self.candidate.as_dict(),
        }


@dataclass(frozen=True)
class SupplierInvoiceInput:
    request_id: str
    source_type: str
    source_path: str | None
    source_hash: str | None
    supplier_name: str | None
    supplier_invoice_ref: str | None
    invoice_date: str | None
    currency: str
    totals: dict[str, Any]
    lines: tuple[SupplierInvoiceLine, ...]
    received_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    @classmethod
    def from_payload(
        cls, request_id: str, payload: dict[str, Any]
    ) -> "SupplierInvoiceInput":
        source_ref = dict(payload.get("source_ref", {}))
        totals = dict(payload.get("totals", {}))
        extracted = dict(payload.get("extracted_invoice", payload))
        lines = tuple(
            SupplierInvoiceLine.from_dict(line)
            for line in extracted.get("lines", payload.get("lines", []))
        )
        return cls(
            request_id=request_id,
            source_type=str(source_ref.get("source_type", payload.get("source_type", "manual"))),
            source_path=_optional_string(source_ref.get("source_path"))
            or _optional_string(payload.get("source_path")),
            source_hash=_optional_string(source_ref.get("source_hash"))
            or _optional_string(payload.get("source_hash")),
            supplier_name=_optional_string(extracted.get("supplier_name"))
            or _optional_string(payload.get("supplier_name")),
            supplier_invoice_ref=_optional_string(extracted.get("supplier_invoice_ref"))
            or _optional_string(payload.get("bill_no"))
            or _optional_string(payload.get("supplier_invoice_ref")),
            invoice_date=_optional_string(extracted.get("invoice_date"))
            or _optional_string(payload.get("posting_date"))
            or _optional_string(payload.get("invoice_date")),
            currency=str(extracted.get("currency", payload.get("currency", "AUD"))),
            totals=totals,
            lines=lines,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "source_type": self.source_type,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "supplier_name": self.supplier_name,
            "supplier_invoice_ref": self.supplier_invoice_ref,
            "invoice_date": self.invoice_date,
            "currency": self.currency,
            "totals": self.totals,
            "lines": [line.as_dict() for line in self.lines],
            "received_at": self.received_at,
        }


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
