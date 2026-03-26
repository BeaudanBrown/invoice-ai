from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


DEV_OPERATOR_ID = "local-dev"
DEV_OPERATOR_TOKEN = "dev-token"


@dataclass(frozen=True)
class DevFixturePaths:
    root: Path
    state_dir: Path
    operators_file: Path
    sample_supplier_invoice_pdf: Path


def prepare_dev_fixtures(root: Path) -> DevFixturePaths:
    root.mkdir(parents=True, exist_ok=True)
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    operators_file = root / "operators.json"
    operators_file.write_text(
        json.dumps(
            {
                "operators": [
                    {
                        "operator_id": DEV_OPERATOR_ID,
                        "token": DEV_OPERATOR_TOKEN,
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    sample_supplier_invoice_pdf = root / "sample-supplier-invoice.pdf"
    sample_supplier_invoice_pdf.write_text(
        "\n".join(
            [
                "Supplier: Spark Wholesale",
                "Invoice Number: INV-2001",
                "Invoice Date: 2026-03-26",
                "Currency: AUD",
                "Switch Replacement | 2 | 12.50 | 25.00",
                "Subtotal: 25.00",
                "Tax: 2.50",
                "Total: 27.50",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return DevFixturePaths(
        root=root,
        state_dir=state_dir,
        operators_file=operators_file,
        sample_supplier_invoice_pdf=sample_supplier_invoice_pdf,
    )


def dev_turn_defaults() -> dict[str, object]:
    return {
        "quote": {
            "company": "Test Company Pty Ltd",
            "customer": "CUST-ACME",
            "customer_name": "Acme",
            "currency": "AUD",
            "labor_item_code": "LABOUR",
            "labor_item_name": "Onsite Labour",
            "travel_item_code": "TRAVEL",
            "travel_item_name": "Travel Surcharge",
            "travel_rate": 25.0,
        },
        "invoice": {
            "company": "Test Company Pty Ltd",
            "customer": "CUST-ACME",
            "customer_name": "Acme",
            "currency": "AUD",
            "labor_item_code": "LABOUR",
            "labor_item_name": "Onsite Labour",
            "travel_item_code": "TRAVEL",
            "travel_item_name": "Travel Surcharge",
            "travel_rate": 25.0,
        },
    }

