from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DocumentSource:
    source_type: str
    source_path: str | None = None
    source_hash: str | None = None
    raw_text: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DocumentSource":
        source_ref = dict(payload.get("source_ref", {}))
        return cls(
            source_type=str(
                source_ref.get("source_type")
                or payload.get("source_type")
                or ("text" if payload.get("raw_text") else "file")
            ),
            source_path=_optional_string(
                source_ref.get("source_path") or payload.get("source_path")
            ),
            source_hash=_optional_string(
                source_ref.get("source_hash") or payload.get("source_hash")
            ),
            raw_text=_optional_string(payload.get("raw_text")),
        )

    def resolved_path(self, *, state_dir: Path) -> Path | None:
        if self.source_path is None:
            return None
        path = Path(self.source_path)
        if path.is_absolute():
            return path
        return state_dir / path

    def computed_hash(self, *, state_dir: Path) -> str | None:
        if self.source_hash is not None:
            return self.source_hash
        if self.raw_text is not None:
            return sha256(self.raw_text.encode("utf-8")).hexdigest()
        resolved = self.resolved_path(state_dir=state_dir)
        if resolved is None or not resolved.exists():
            return None
        return sha256(resolved.read_bytes()).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "raw_text": self.raw_text,
        }


@dataclass(frozen=True)
class ExtractedInvoiceLine:
    description: str
    qty: float
    rate: float
    amount: float
    item_code: str | None = None
    item_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "description": self.description,
            "qty": self.qty,
            "rate": self.rate,
            "amount": self.amount,
            "item_code": self.item_code,
            "item_name": self.item_name,
        }


@dataclass(frozen=True)
class ExtractionCandidate:
    supplier_name: str | None
    supplier_invoice_ref: str | None
    invoice_date: str | None
    currency: str
    totals: dict[str, Any]
    lines: tuple[ExtractedInvoiceLine, ...]
    confidence: float
    warnings: tuple[str, ...] = field(default_factory=tuple)
    anomalies: tuple[str, ...] = field(default_factory=tuple)
    extracted_text: str | None = None

    def as_extracted_invoice(self) -> dict[str, Any]:
        return {
            "supplier_name": self.supplier_name,
            "supplier_invoice_ref": self.supplier_invoice_ref,
            "invoice_date": self.invoice_date,
            "currency": self.currency,
            "totals": self.totals,
            "lines": [line.as_dict() for line in self.lines],
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.as_extracted_invoice(),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
            "anomalies": list(self.anomalies),
            "extracted_text": self.extracted_text,
        }


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
