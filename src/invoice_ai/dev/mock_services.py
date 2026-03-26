from __future__ import annotations

from datetime import date
import json
from typing import Any

from fastapi import FastAPI, Request


def create_mock_docling_app() -> FastAPI:
    app = FastAPI(title="invoice-ai-mock-docling")

    @app.post("/extract")
    async def extract(payload: dict[str, Any]) -> dict[str, Any]:
        source_path = str(payload["source_path"])
        with open(source_path, "r", encoding="utf-8") as handle:
            return {"document_text": handle.read()}

    return app


def create_mock_erp_app() -> FastAPI:
    app = FastAPI(title="invoice-ai-mock-erp")
    app.state.db = _seed_database()
    app.state.counters = {
        "Quotation": 0,
        "Sales Invoice": 0,
        "Purchase Invoice": 0,
        "File": 0,
    }

    @app.get("/api/resource/{doctype}")
    async def list_docs(
        doctype: str,
        filters: str | None = None,
        fields: str | None = None,
        order_by: str | None = None,
        limit_page_length: int = 20,
    ) -> dict[str, Any]:
        documents = list(app.state.db.get(doctype, {}).values())
        parsed_filters = _decode_json_object(filters)
        if parsed_filters:
            documents = [
                doc for doc in documents if _matches_filters(doc, parsed_filters)
            ]
        if order_by == "modified desc":
            documents.sort(key=lambda doc: str(doc.get("modified") or ""), reverse=True)
        documents = documents[:limit_page_length]
        parsed_fields = _decode_json_list(fields)
        if parsed_fields:
            documents = [_select_fields(doc, parsed_fields) for doc in documents]
        return {"data": documents}

    @app.get("/api/resource/{doctype}/{name}")
    async def get_doc(doctype: str, name: str) -> dict[str, Any]:
        document = app.state.db.get(doctype, {}).get(name)
        if document is None:
            return {"data": {}}
        return {"data": document}

    @app.post("/api/resource/{doctype}")
    async def create_doc(doctype: str, payload: dict[str, Any]) -> dict[str, Any]:
        document = _normalize_new_doc(
            doctype=doctype,
            payload=payload,
            db=app.state.db,
            counters=app.state.counters,
        )
        app.state.db.setdefault(doctype, {})[document["name"]] = document
        _refresh_child_tables(doctype=doctype, document=document, db=app.state.db)
        return {"data": document}

    @app.put("/api/resource/{doctype}/{name}")
    async def update_doc(doctype: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        existing = dict(app.state.db.get(doctype, {}).get(name) or {})
        updated = _normalize_existing_doc(
            doctype=doctype,
            existing=existing,
            payload=payload,
            db=app.state.db,
        )
        app.state.db.setdefault(doctype, {})[name] = updated
        _refresh_child_tables(doctype=doctype, document=updated, db=app.state.db)
        return {"data": updated}

    @app.post("/api/method/upload_file")
    async def upload_file(_request: Request) -> dict[str, Any]:
        app.state.counters["File"] += 1
        name = f"FILE-{app.state.counters['File']:04d}"
        return {"message": {"name": name, "file_url": f"/files/{name}.bin"}}

    return app


def _seed_database() -> dict[str, dict[str, dict[str, Any]]]:
    today = date.today().isoformat()
    return {
        "Customer": {
            "CUST-ACME": {
                "doctype": "Customer",
                "name": "CUST-ACME",
                "customer_name": "Acme",
                "customer_group": "Commercial",
                "territory": "Australia",
                "modified": today,
            }
        },
        "Supplier": {
            "SUP-SPARK": {
                "doctype": "Supplier",
                "name": "SUP-SPARK",
                "supplier_name": "Spark Wholesale",
                "modified": today,
            }
        },
        "Item": {
            "LABOUR": {
                "doctype": "Item",
                "name": "LABOUR",
                "item_code": "LABOUR",
                "item_name": "Onsite Labour",
                "stock_uom": "Hour",
                "modified": today,
            },
            "TRAVEL": {
                "doctype": "Item",
                "name": "TRAVEL",
                "item_code": "TRAVEL",
                "item_name": "Travel Surcharge",
                "stock_uom": "Unit",
                "modified": today,
            },
            "SWITCH": {
                "doctype": "Item",
                "name": "SWITCH",
                "item_code": "SWITCH",
                "item_name": "Switch Replacement",
                "stock_uom": "Unit",
                "modified": today,
            },
        },
        "Item Price": {
            "PRICE-LABOUR": {
                "doctype": "Item Price",
                "name": "PRICE-LABOUR",
                "item_code": "LABOUR",
                "price_list": "Standard Selling",
                "price_list_rate": 95.0,
                "currency": "AUD",
                "modified": today,
            },
            "PRICE-TRAVEL": {
                "doctype": "Item Price",
                "name": "PRICE-TRAVEL",
                "item_code": "TRAVEL",
                "price_list": "Standard Selling",
                "price_list_rate": 25.0,
                "currency": "AUD",
                "modified": today,
            },
            "PRICE-SWITCH": {
                "doctype": "Item Price",
                "name": "PRICE-SWITCH",
                "item_code": "SWITCH",
                "price_list": "Standard Selling",
                "price_list_rate": 20.0,
                "currency": "AUD",
                "modified": today,
            },
        },
        "Pricing Rule": {},
        "Project": {},
        "Quotation": {},
        "Sales Invoice": {},
        "Purchase Invoice": {},
        "Sales Invoice Item": {
            "SINV-ITEM-0001": {
                "doctype": "Sales Invoice Item",
                "name": "SINV-ITEM-0001",
                "parent": "SINV-HIST-0001",
                "item_code": "LABOUR",
                "rate": 90.0,
                "amount": 180.0,
                "modified": today,
            }
        },
        "Purchase Invoice Item": {
            "PINV-ITEM-0001": {
                "doctype": "Purchase Invoice Item",
                "name": "PINV-ITEM-0001",
                "parent": "PINV-HIST-0001",
                "item_code": "SWITCH",
                "rate": 12.5,
                "amount": 25.0,
                "modified": today,
            }
        },
    }


def _decode_json_object(raw: str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, dict) else {}


def _decode_json_list(raw: str | None) -> list[str]:
    if raw is None:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _matches_filters(document: dict[str, Any], filters: dict[str, Any]) -> bool:
    for key, value in filters.items():
        if document.get(key) != value:
            return False
    return True


def _select_fields(document: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    selected = {field: document.get(field) for field in fields}
    selected.setdefault("name", document.get("name"))
    return selected


def _normalize_new_doc(
    *,
    doctype: str,
    payload: dict[str, Any],
    db: dict[str, dict[str, dict[str, Any]]],
    counters: dict[str, int],
) -> dict[str, Any]:
    counters[doctype] = counters.get(doctype, 0) + 1
    name = {
        "Quotation": f"QUO-{counters[doctype]:04d}",
        "Sales Invoice": f"SINV-{counters[doctype]:04d}",
        "Purchase Invoice": f"PINV-{counters[doctype]:04d}",
    }.get(doctype, f"{doctype.upper()}-{counters[doctype]:04d}")
    existing = {"doctype": doctype, "name": name}
    return _normalize_existing_doc(
        doctype=doctype,
        existing=existing,
        payload=payload,
        db=db,
    )


def _normalize_existing_doc(
    *,
    doctype: str,
    existing: dict[str, Any],
    payload: dict[str, Any],
    db: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    normalized = dict(existing)
    normalized.update(payload)
    normalized["doctype"] = doctype
    normalized["name"] = str(existing["name"])
    normalized.setdefault("docstatus", 0)
    normalized["modified"] = date.today().isoformat()

    if doctype == "Quotation":
        normalized.setdefault("party_name", normalized.get("customer"))
        normalized.setdefault("customer_name", normalized.get("party_name"))
        normalized["items"] = _normalize_items(normalized, db)
        normalized["grand_total"] = _grand_total(normalized["items"])
        normalized.setdefault("transaction_date", date.today().isoformat())

    if doctype == "Sales Invoice":
        if normalized.get("customer") is None and normalized.get("quotation"):
            quotation = db.get("Quotation", {}).get(str(normalized["quotation"]))
            if quotation is not None:
                normalized["customer"] = quotation.get("party_name")
        normalized["items"] = _normalize_items(normalized, db)
        normalized["grand_total"] = _grand_total(normalized["items"])
        normalized.setdefault("posting_date", date.today().isoformat())

    if doctype == "Purchase Invoice":
        normalized["items"] = _normalize_items(normalized, db)
        normalized["grand_total"] = _grand_total(normalized["items"])
        normalized.setdefault("posting_date", date.today().isoformat())

    return normalized


def _normalize_items(
    document: dict[str, Any], db: dict[str, dict[str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, item in enumerate(document.get("items", []), start=1):
        normalized = dict(item)
        item_code = normalized.get("item_code")
        if item_code is not None:
            item_doc = db.get("Item", {}).get(str(item_code))
            if item_doc is not None:
                normalized.setdefault("item_name", item_doc.get("item_name"))
        normalized.setdefault("name", f"{document['name']}-ITEM-{index:04d}")
        normalized.setdefault(
            "description",
            normalized.get("item_name") or normalized.get("item_code") or "Line Item",
        )
        normalized["qty"] = float(normalized.get("qty") or 0)
        normalized["rate"] = float(normalized.get("rate") or 0)
        normalized["amount"] = round(normalized["qty"] * normalized["rate"], 2)
        items.append(normalized)
    return items


def _grand_total(items: list[dict[str, Any]]) -> float:
    return round(sum(float(item.get("amount") or 0) for item in items), 2)


def _refresh_child_tables(
    *, doctype: str, document: dict[str, Any], db: dict[str, dict[str, dict[str, Any]]]
) -> None:
    child_doctype = None
    if doctype == "Sales Invoice":
        child_doctype = "Sales Invoice Item"
    elif doctype == "Purchase Invoice":
        child_doctype = "Purchase Invoice Item"
    if child_doctype is None:
        return

    child_table = db.setdefault(child_doctype, {})
    for key in [key for key, value in child_table.items() if value.get("parent") == document["name"]]:
        child_table.pop(key, None)
    for item in document.get("items", []):
        child_table[str(item["name"])] = {
            "doctype": child_doctype,
            "name": str(item["name"]),
            "parent": document["name"],
            "item_code": item.get("item_code"),
            "rate": item.get("rate"),
            "amount": item.get("amount"),
            "modified": document.get("modified"),
        }

