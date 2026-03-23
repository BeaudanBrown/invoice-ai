from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Any

from .models import ExtractionCandidate, ExtractedInvoiceLine

LINE_PATTERN = re.compile(
    r"^(?P<description>.+?)\s+\|\s+(?P<qty>\d+(?:\.\d+)?)\s+\|\s+(?P<rate>\d+(?:\.\d+)?)\s+\|\s+(?P<amount>\d+(?:\.\d+)?)$"
)


def parse_supplier_invoice_text(text: str) -> ExtractionCandidate:
    stripped = text.strip()
    if stripped.startswith("{"):
        parsed = _from_json_payload(json.loads(stripped))
        if parsed is not None:
            return parsed

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    supplier_name = _match_value(lines, ["supplier", "vendor", "from"])
    supplier_invoice_ref = _match_value(
        lines,
        ["invoice number", "invoice no", "invoice ref", "invoice #", "bill no"],
    )
    invoice_date = _normalize_date(_match_value(lines, ["invoice date", "date"]))
    currency = _match_currency(text)
    totals = {
        "subtotal": _match_amount(lines, ["subtotal"]),
        "tax": _match_amount(lines, ["tax", "gst", "vat"]),
        "grand_total": _match_amount(lines, ["total", "amount due"]),
    }
    extracted_lines = tuple(_parse_lines(lines))

    warnings: list[str] = []
    confidence = 0.25
    if supplier_name:
        confidence += 0.2
    else:
        warnings.append("Supplier name was not confidently extracted")
    if supplier_invoice_ref:
        confidence += 0.15
    else:
        warnings.append("Invoice reference was not confidently extracted")
    if invoice_date:
        confidence += 0.15
    else:
        warnings.append("Invoice date was not confidently extracted")
    if extracted_lines:
        confidence += 0.25
    else:
        warnings.append("No line items were confidently extracted")
    if totals.get("grand_total") is not None:
        confidence += 0.1
    else:
        warnings.append("Invoice total was not confidently extracted")

    if supplier_name is None and lines:
        supplier_name = lines[0]
        warnings.append("Fell back to the first non-empty line for supplier name")

    return ExtractionCandidate(
        supplier_name=supplier_name,
        supplier_invoice_ref=supplier_invoice_ref,
        invoice_date=invoice_date,
        currency=currency,
        totals={key: value for key, value in totals.items() if value is not None},
        lines=extracted_lines,
        confidence=min(round(confidence, 2), 1.0),
        warnings=tuple(dict.fromkeys(warnings)),
        extracted_text=text,
    )


def _from_json_payload(payload: dict[str, Any]) -> ExtractionCandidate | None:
    extracted = dict(payload.get("extracted_invoice", payload))
    raw_lines = extracted.get("lines")
    if not isinstance(raw_lines, list):
        return None
    lines = []
    for line in raw_lines:
        if not isinstance(line, dict):
            continue
        qty = float(line.get("qty", 0))
        rate = float(line.get("rate", 0))
        amount = line.get("amount")
        lines.append(
            ExtractedInvoiceLine(
                description=str(line.get("description", "")),
                qty=qty,
                rate=rate,
                amount=float(amount if amount is not None else qty * rate),
                item_code=_optional_string(line.get("item_code")),
                item_name=_optional_string(line.get("item_name")),
            )
        )
    return ExtractionCandidate(
        supplier_name=_optional_string(extracted.get("supplier_name")),
        supplier_invoice_ref=_optional_string(
            extracted.get("supplier_invoice_ref") or extracted.get("bill_no")
        ),
        invoice_date=_normalize_date(_optional_string(extracted.get("invoice_date"))),
        currency=str(extracted.get("currency", "AUD")),
        totals=dict(extracted.get("totals", {})),
        lines=tuple(lines),
        confidence=float(extracted.get("confidence", 0.95)),
        warnings=tuple(str(item) for item in extracted.get("warnings", [])),
        extracted_text=json.dumps(payload, indent=2, sort_keys=True),
    )


def _match_value(lines: list[str], keys: list[str]) -> str | None:
    for line in lines:
        lowered = line.lower()
        for key in keys:
            if lowered.startswith(f"{key}:"):
                return line.split(":", 1)[1].strip() or None
            if lowered.startswith(f"{key} "):
                return line[len(key) :].strip(" :-") or None
    return None


def _match_amount(lines: list[str], keys: list[str]) -> float | None:
    amount_pattern = re.compile(r"(-?\d+(?:,\d{3})*(?:\.\d+)?)")
    for line in lines:
        lowered = line.lower()
        if any(
            lowered.startswith(f"{key}:")
            or lowered.startswith(f"{key} ")
            or lowered == key
            for key in keys
        ):
            matches = amount_pattern.findall(line.replace("$", ""))
            if matches:
                return float(matches[-1].replace(",", ""))
    return None


def _match_currency(text: str) -> str:
    upper = text.upper()
    if "USD" in upper:
        return "USD"
    if "EUR" in upper:
        return "EUR"
    return "AUD"


def _parse_lines(lines: list[str]) -> list[ExtractedInvoiceLine]:
    extracted: list[ExtractedInvoiceLine] = []
    for line in lines:
        match = LINE_PATTERN.match(line)
        if not match:
            continue
        qty = float(match.group("qty"))
        rate = float(match.group("rate"))
        amount = float(match.group("amount"))
        extracted.append(
            ExtractedInvoiceLine(
                description=match.group("description").strip(),
                qty=qty,
                rate=rate,
                amount=amount,
                item_name=match.group("description").strip(),
            )
        )
    return extracted


def _normalize_date(value: str | None) -> str | None:
    if value is None:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
