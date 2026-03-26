from __future__ import annotations

import re
from typing import Any

from .models import PlannerAttachment, PlannerTurn
from .suggestions import is_memory_only_turn


class PlannerParseError(ValueError):
    pass


def plan_operator_request(turn: PlannerTurn) -> dict[str, Any]:
    review_action = _review_action_payload(turn.message)
    if review_action is not None:
        return review_action

    review_queue = _review_queue_payload(turn.message)
    if review_queue is not None:
        return {
            "request_kind": "review_queue",
            "message": turn.message,
            "review_queue": review_queue,
        }

    if is_memory_only_turn(turn.message):
        return {
            "request_kind": "memory_suggestion",
            "message": turn.message,
        }

    if _has_supplier_attachment(turn.attachments):
        return {
            "request_kind": "supplier_document_intake",
            "message": turn.message,
            "supplier_document": _supplier_payload(turn),
        }

    if _looks_like_quote_revision(turn):
        return {
            "request_kind": "quote_revision",
            "message": turn.message,
            **_quote_revision_payload(turn),
        }

    if _looks_like_invoice_revision(turn):
        return {
            "request_kind": "invoice_revision",
            "message": turn.message,
            **_invoice_revision_payload(turn),
        }

    if _looks_like_invoice_draft(turn):
        return {
            "request_kind": "invoice_draft",
            "message": turn.message,
            "invoice": _invoice_draft_payload(turn),
        }

    if _looks_like_quote_draft(turn):
        return {
            "request_kind": "quote_draft",
            "message": turn.message,
            "quote": _quote_draft_payload(turn),
        }

    raise PlannerParseError(
        "Planner could not safely classify the operator turn into a supported request"
    )


def _review_queue_payload(message: str) -> dict[str, Any] | None:
    lower = message.lower()
    if "review" not in lower:
        return None
    if not any(token in lower for token in ("show", "list", "what", "pending", "queue")):
        return None

    payload: dict[str, Any] = {"status": "pending"}
    if "accepted" in lower:
        payload["status"] = "accepted"
    elif "rejected" in lower:
        payload["status"] = "rejected"
    elif "all" in lower:
        payload.pop("status", None)

    if "client" in lower:
        payload["scope"] = "clients"
    elif "supplier" in lower:
        payload["scope"] = "suppliers"
    elif "job" in lower:
        payload["scope"] = "jobs"
    elif "operator" in lower:
        payload["scope"] = "operator"
    elif "global" in lower:
        payload["scope"] = "global"
    return payload


def _review_action_payload(message: str) -> dict[str, Any] | None:
    review_id = _extract_review_id(message)
    if review_id is None:
        return None
    lower = message.lower()

    if any(token in lower for token in ("accept review", "approve review", "accept ", "approve ")):
        payload = {"request_kind": "review_accept", "message": message, "review_accept": {"review_id": review_id}}
        decision_note = _extract_decision_note(message)
        if decision_note is not None:
            payload["review_accept"]["decision_note"] = decision_note
        return payload

    if any(token in lower for token in ("reject review", "decline review", "reject ", "decline ")):
        payload = {"request_kind": "review_reject", "message": message, "review_reject": {"review_id": review_id}}
        decision_note = _extract_decision_note(message)
        if decision_note is not None:
            payload["review_reject"]["decision_note"] = decision_note
        return payload

    if any(token in lower for token in ("show review", "inspect review", "open review", "review ")):
        return {
            "request_kind": "review_detail",
            "message": message,
            "review": {"review_id": review_id},
        }
    return None


def _extract_review_id(message: str) -> str | None:
    match = re.search(r"\b(memory-suggestion-[a-z0-9]+)\b", message, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1)


def _extract_decision_note(message: str) -> str | None:
    match = re.search(r"\b(?:because|with note|note)\b[: ]+(.*)$", message, re.IGNORECASE)
    if match is None:
        return None
    note = match.group(1).strip().strip(".")
    return note or None


def _has_supplier_attachment(attachments: tuple[PlannerAttachment, ...]) -> bool:
    return any(
        attachment.kind in {"supplier_invoice", "document", "invoice_document"}
        for attachment in attachments
    )


def _supplier_payload(turn: PlannerTurn) -> dict[str, Any]:
    for attachment in turn.attachments:
        if attachment.kind not in {"supplier_invoice", "document", "invoice_document"}:
            continue
        payload = dict(attachment.payload)
        if "document_path" in payload or "raw_text" in payload:
            return payload
    raise PlannerParseError(
        "Supplier document intake requires an attachment with document_path or raw_text"
    )


def _looks_like_quote_revision(turn: PlannerTurn) -> bool:
    message = turn.message.lower()
    if "invoice" in message:
        return False
    if turn.active_quote():
        return True
    return any(
        token in message
        for token in ("revise", "update quote", "change quote", "add ", "make it", "split ")
    )


def _looks_like_quote_draft(turn: PlannerTurn) -> bool:
    message = turn.message.lower()
    if "invoice" in message:
        return False
    return "quote" in message or "draft a quote" in message


def _looks_like_invoice_revision(turn: PlannerTurn) -> bool:
    if turn.active_invoice():
        return True
    message = turn.message.lower()
    return any(
        token in message
        for token in ("revise invoice", "update invoice", "change invoice", "add to invoice")
    )


def _looks_like_invoice_draft(turn: PlannerTurn) -> bool:
    message = turn.message.lower()
    return (
        "invoice" in message
        or "draft an invoice" in message
        or "bill " in message
    ) and "supplier invoice" not in message


def _quote_draft_payload(turn: PlannerTurn) -> dict[str, Any]:
    quote_defaults = dict(turn.defaults.get("quote", {}))
    company = quote_defaults.get("company")
    if not company:
        raise PlannerParseError("Quote drafting requires defaults.quote.company")

    customer = _extract_customer_from_quote(turn.message)
    if customer is None and quote_defaults.get("customer") is None:
        raise PlannerParseError("Quote drafting requires an identifiable customer")
    customer_name = quote_defaults.get("customer_name") or customer

    line_items = _extract_quote_line_items(turn.message, quote_defaults)
    if not line_items:
        raise PlannerParseError("Quote drafting requires at least one inferred line item")

    return {
        "draft_key": str(quote_defaults.get("draft_key") or turn.request_id),
        "customer": quote_defaults.get("customer") or customer,
        "customer_name": customer_name,
        "company": company,
        "currency": str(quote_defaults.get("currency") or "AUD"),
        "narrative": {
            "intro": str(quote_defaults.get("intro") or "Quote Draft"),
            "notes": str(quote_defaults.get("notes") or ""),
        },
        "line_items": line_items,
    }


def _quote_revision_payload(turn: PlannerTurn) -> dict[str, Any]:
    active_quote = turn.active_quote()
    patch = _extract_quote_revision_patch(turn.message, turn.defaults)
    if not patch:
        raise PlannerParseError("Planner could not infer a safe quote revision patch")

    payload: dict[str, Any] = {
        "patch": patch,
        "summary": _revision_summary(turn.message),
    }
    if active_quote.get("draft_key") is not None:
        payload["draft_key"] = active_quote["draft_key"]
    if active_quote.get("quotation") is not None:
        payload["quotation"] = active_quote["quotation"]
    return payload


def _invoice_draft_payload(turn: PlannerTurn) -> dict[str, Any]:
    invoice_defaults = dict(turn.defaults.get("invoice", {}))
    quote_defaults = dict(turn.defaults.get("quote", {}))
    company = invoice_defaults.get("company") or quote_defaults.get("company")
    if not company:
        raise PlannerParseError("Sales invoice drafting requires defaults.invoice.company")

    quotation = _extract_quotation_reference(turn.message)
    if quotation is None:
        active_quote = turn.active_quote()
        if active_quote.get("quotation") is not None:
            quotation = str(active_quote["quotation"])
    customer = _extract_customer_from_invoice(turn.message)
    configured_customer = invoice_defaults.get("customer") or quote_defaults.get("customer")
    if quotation is None and customer is None and configured_customer is None:
        raise PlannerParseError(
            "Sales invoice drafting requires an identifiable customer or quotation"
        )

    line_items = []
    if quotation is None:
        line_items = _extract_quote_line_items(turn.message, {**quote_defaults, **invoice_defaults})
        if not line_items:
            raise PlannerParseError(
                "Sales invoice drafting requires at least one inferred line item when not invoicing from a quotation"
            )

    return {
        "draft_key": str(invoice_defaults.get("draft_key") or turn.request_id),
        "quotation": quotation,
        "customer": configured_customer or customer,
        "customer_name": invoice_defaults.get("customer_name") or quote_defaults.get("customer_name") or customer,
        "company": company,
        "currency": str(invoice_defaults.get("currency") or quote_defaults.get("currency") or "AUD"),
        "narrative": {
            "intro": str(invoice_defaults.get("intro") or "Sales Invoice Draft"),
            "notes": str(invoice_defaults.get("notes") or ""),
        },
        "line_items": line_items,
    }


def _invoice_revision_payload(turn: PlannerTurn) -> dict[str, Any]:
    active_invoice = turn.active_invoice()
    patch = _extract_quote_revision_patch(turn.message, turn.defaults)
    if not patch:
        raise PlannerParseError("Planner could not infer a safe sales invoice revision patch")

    payload: dict[str, Any] = {
        "patch": patch,
        "summary": _revision_summary(turn.message),
    }
    if active_invoice.get("draft_key") is not None:
        payload["draft_key"] = active_invoice["draft_key"]
    if active_invoice.get("sales_invoice") is not None:
        payload["sales_invoice"] = active_invoice["sales_invoice"]
    return payload


def _extract_customer_from_quote(message: str) -> str | None:
    match = re.search(r"\bquote\s+(.+?)\s+for\b", message, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _extract_customer_from_invoice(message: str) -> str | None:
    invoice_match = re.search(r"\binvoice\s+(.+?)\s+for\b", message, flags=re.IGNORECASE)
    if invoice_match:
        return invoice_match.group(1).strip()
    bill_match = re.search(r"\bbill\s+(.+?)\s+for\b", message, flags=re.IGNORECASE)
    if bill_match:
        return bill_match.group(1).strip()
    return None


def _extract_quotation_reference(message: str) -> str | None:
    match = re.search(r"\bquote(?:\s+|:)([A-Z0-9-]+)\b", message, flags=re.IGNORECASE)
    if match and any(char.isdigit() for char in match.group(1)):
        return match.group(1)
    match = re.search(r"\bquotation(?:\s+|:)([A-Z0-9-]+)\b", message, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_quote_line_items(message: str, defaults: dict[str, Any]) -> list[dict[str, Any]]:
    lower = message.lower()
    items: list[dict[str, Any]] = []

    hour_matches = re.findall(
        r"(\d+(?:\.\d+)?)\s+(?:hours?|hrs?)\b(?:\s+([a-z][a-z\s-]+?))?(?=$|\s+and\s+|\s+plus\s+|,)",
        lower,
        flags=re.IGNORECASE,
    )
    labor_item_code = defaults.get("labor_item_code")
    labor_item_name = defaults.get("labor_item_name")
    for qty_text, descriptor in hour_matches:
        desc = "Labour"
        if descriptor.strip():
            desc = descriptor.strip().replace(" onsite", " onsite").title()
        elif defaults.get("labor_description"):
            desc = str(defaults["labor_description"])
        items.append(
            {
                "item_code": labor_item_code,
                "item_name": labor_item_name,
                "description": desc,
                "qty": float(qty_text),
            }
        )

    if "travel" in lower:
        items.append(
            {
                "item_code": defaults.get("travel_item_code"),
                "item_name": defaults.get("travel_item_name"),
                "description": str(defaults.get("travel_description") or "Travel"),
                "qty": 1.0,
                "rate": defaults.get("travel_rate"),
            }
        )

    return items


def _extract_quote_revision_patch(message: str, defaults: dict[str, Any]) -> dict[str, Any]:
    lower = message.lower()
    patch: dict[str, Any] = {}

    if "travel" in lower and any(token in lower for token in ("add", "split", "include")):
        patch["items"] = [
            {
                "item_code": defaults.get("quote", {}).get("travel_item_code")
                or defaults.get("travel_item_code"),
                "description": str(
                    defaults.get("quote", {}).get("travel_description")
                    or defaults.get("travel_description")
                    or "Travel"
                ),
                "qty": 1.0,
                "rate": (
                    defaults.get("quote", {}).get("travel_rate")
                    if isinstance(defaults.get("quote"), dict)
                    else None
                )
                or defaults.get("travel_rate"),
            }
        ]
        patch["replace_items"] = False

    note_match = re.search(r"(?:note|notes?)[:\s]+(.+)$", message, flags=re.IGNORECASE)
    if note_match:
        patch["notes_append"] = [note_match.group(1).strip()]

    return patch


def _revision_summary(message: str) -> str:
    text = message.strip()
    return text[:1].upper() + text[1:] if text else "Quote draft revised"
