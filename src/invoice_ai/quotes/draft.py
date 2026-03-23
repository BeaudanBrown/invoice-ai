from __future__ import annotations

from typing import Any

from ..artifacts.models import QuotePreview


def quotation_payload_from_context(
    *,
    customer_name: str,
    company: str,
    currency: str,
    narrative: dict[str, str],
    line_items: list[dict[str, Any]],
    source_refs: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    return {
        "customer": customer_name,
        "company": company,
        "currency": currency,
        "items": [
            {
                "item_code": item["item_code"],
                "qty": item["qty"],
                "rate": item["rate"],
                "description": item["description"],
            }
            for item in line_items
        ],
        "narrative": narrative,
        "source_refs": list(source_refs),
    }


def preview_from_quotation_doc(*, draft_key: str, quotation_doc: dict[str, Any]) -> QuotePreview:
    customer = str(
        quotation_doc.get("party_name")
        or quotation_doc.get("customer_name")
        or quotation_doc.get("customer")
        or ""
    )
    company = str(quotation_doc.get("company") or "")
    currency = str(quotation_doc.get("currency") or "AUD")
    return QuotePreview.from_dict(
        {
            "draft_key": draft_key,
            "customer": customer,
            "company": company,
            "currency": currency,
            "narrative": {
                "intro": quotation_doc.get("remarks") or "Quote Draft",
                "notes": quotation_doc.get("terms") or "",
            },
            "items": [
                {
                    "item_code": item.get("item_code", ""),
                    "qty": item.get("qty", 0),
                    "rate": item.get("rate", 0),
                    "description": item.get("description", ""),
                }
                for item in quotation_doc.get("items", [])
            ],
        }
    )
