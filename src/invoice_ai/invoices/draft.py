from __future__ import annotations

from typing import Any

from ..artifacts.models import SalesInvoicePreview


def sales_invoice_payload_from_context(
    *,
    customer_name: str,
    company: str,
    currency: str,
    narrative: dict[str, str],
    line_items: list[dict[str, Any]],
    source_refs: tuple[dict[str, Any], ...],
    source_quotation: str | None,
) -> dict[str, Any]:
    return {
        "customer": customer_name,
        "company": company,
        "currency": currency,
        "items": [
            {
                "item_code": item.get("item_code"),
                "qty": item.get("qty"),
                "rate": item.get("rate"),
                "description": item.get("description"),
                **(
                    {"quotation": item.get("quotation"), "quotation_item": item.get("quotation_item")}
                    if item.get("quotation")
                    else {}
                ),
            }
            for item in line_items
        ],
        "narrative": narrative,
        "source_refs": list(source_refs),
        "quotation": source_quotation,
    }


def preview_from_sales_invoice_doc(
    *, draft_key: str, sales_invoice_doc: dict[str, Any]
) -> SalesInvoicePreview:
    customer = str(
        sales_invoice_doc.get("customer_name")
        or sales_invoice_doc.get("customer")
        or ""
    )
    company = str(sales_invoice_doc.get("company") or "")
    currency = str(sales_invoice_doc.get("currency") or "AUD")
    return SalesInvoicePreview.from_dict(
        {
            "draft_key": draft_key,
            "customer": customer,
            "company": company,
            "currency": currency,
            "narrative": {
                "intro": sales_invoice_doc.get("remarks") or "Sales Invoice Draft",
                "notes": sales_invoice_doc.get("terms") or "",
            },
            "items": [
                {
                    "item_code": item.get("item_code", ""),
                    "qty": item.get("qty", 0),
                    "rate": item.get("rate", 0),
                    "description": item.get("description", ""),
                }
                for item in sales_invoice_doc.get("items", [])
            ],
        }
    )
