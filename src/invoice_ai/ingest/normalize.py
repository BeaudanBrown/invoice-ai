from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..erp.client import ERPNextClient
from .models import ItemCandidate, SupplierCandidate, SupplierInvoiceInput


class SupplierInvoiceNormalizer:
    def __init__(self, client: ERPNextClient | None = None) -> None:
        self.client = client

    def normalize(self, source: SupplierInvoiceInput) -> dict[str, Any]:
        supplier_candidate = self._resolve_supplier(source.supplier_name)

        normalized_lines = []
        missing_items: list[dict[str, Any]] = []
        for line in source.lines:
            candidate = self._resolve_item(line.lookup_label(), line.item_code, line.item_name)
            normalized_line = replace(line, candidate=candidate)
            normalized_lines.append(normalized_line)
            if not candidate.matched:
                missing_items.append(
                    {
                        "source_label": candidate.source_label,
                        "description": line.description,
                        "qty": line.qty,
                        "rate": line.rate,
                    }
                )

        resolved = supplier_candidate.matched and not missing_items
        purchase_invoice_payload = None
        if resolved:
            purchase_invoice_payload = {
                "supplier": supplier_candidate.supplier_id,
                "bill_no": source.supplier_invoice_ref,
                "posting_date": source.invoice_date,
                "items": [
                    {
                        "item_code": line.candidate.item_code,
                        "qty": line.qty,
                        "rate": line.rate,
                        "description": line.description,
                    }
                    for line in normalized_lines
                    if line.candidate is not None and line.candidate.item_code is not None
                ],
                "source_ref": {
                    "source_type": source.source_type,
                    "source_path": source.source_path,
                    "source_hash": source.source_hash,
                },
            }

        return {
            "supplier": supplier_candidate.as_dict(),
            "invoice": {
                "supplier_invoice_ref": source.supplier_invoice_ref,
                "invoice_date": source.invoice_date,
                "currency": source.currency,
                "totals": source.totals,
            },
            "lines": [line.as_dict() for line in normalized_lines],
            "resolved": resolved,
            "purchase_invoice_payload": purchase_invoice_payload,
            "missing_master_data": {
                "supplier": None
                if supplier_candidate.matched
                else {"supplier_name": source.supplier_name},
                "items": missing_items,
            },
        }

    def _resolve_supplier(self, supplier_name: str | None) -> SupplierCandidate:
        if supplier_name is None:
            return SupplierCandidate(
                supplier_name="",
                supplier_id=None,
                confidence=0.0,
                matched=False,
            )
        if self.client is None:
            return SupplierCandidate(
                supplier_name=supplier_name,
                supplier_id=None,
                confidence=0.0,
                matched=False,
            )

        docs = self.client.list_docs(
            "Supplier",
            filters={"supplier_name": supplier_name},
            fields=["name", "supplier_name"],
            limit=2,
        )
        if len(docs) == 1:
            return SupplierCandidate(
                supplier_name=supplier_name,
                supplier_id=str(docs[0]["name"]),
                confidence=1.0,
                matched=True,
            )
        return SupplierCandidate(
            supplier_name=supplier_name,
            supplier_id=None,
            confidence=0.0,
            matched=False,
        )

    def _resolve_item(
        self, label: str, item_code: str | None, item_name: str | None
    ) -> ItemCandidate:
        if self.client is None:
            return ItemCandidate(source_label=label, item_code=item_code, matched=False)

        if item_code:
            docs = self.client.list_docs(
                "Item",
                filters={"item_code": item_code},
                fields=["name", "item_code", "item_name"],
                limit=2,
            )
            if len(docs) == 1:
                return ItemCandidate(
                    source_label=label,
                    item_code=str(docs[0].get("item_code") or docs[0]["name"]),
                    confidence=1.0,
                    matched=True,
                )

        if item_name:
            docs = self.client.list_docs(
                "Item",
                filters={"item_name": item_name},
                fields=["name", "item_code", "item_name"],
                limit=2,
            )
            if len(docs) == 1:
                return ItemCandidate(
                    source_label=label,
                    item_code=str(docs[0].get("item_code") or docs[0]["name"]),
                    confidence=0.9,
                    matched=True,
                )

        return ItemCandidate(
            source_label=label,
            item_code=item_code,
            confidence=0.0,
            matched=False,
        )
