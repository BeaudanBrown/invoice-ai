from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..control_plane.store import ControlPlaneStore
from ..persistence import (
    IngestComposedResultRecord,
    IngestExtractedRecord,
    IngestProcessedRecord,
    IngestRejectedRecord,
    IngestSourceRecord,
)


class IngestStore:
    def __init__(
        self,
        ingest_dir: Path,
        *,
        control_plane: ControlPlaneStore | None = None,
    ) -> None:
        self.ingest_dir = ingest_dir
        self.control_plane = control_plane

    def write_processed(
        self,
        *,
        request_id: str,
        source: dict[str, Any],
        normalized: dict[str, Any],
    ) -> Path:
        record_dir = self._record_dir("processed", request_id)
        record_dir.mkdir(parents=True, exist_ok=True)
        processed = IngestProcessedRecord(
            request_id=request_id,
            source=source,
            proposal=normalized,
        )
        (record_dir / "source.json").write_text(
            IngestSourceRecord(request_id=request_id, source=source).to_json_text() + "\n",
            encoding="utf-8",
        )
        (record_dir / "proposal.json").write_text(processed.to_json_text() + "\n", encoding="utf-8")
        self._upsert_index(
            request_id=request_id,
            record_dir=record_dir,
            source=source,
            proposal=normalized,
        )
        return record_dir

    def write_extracted(
        self,
        *,
        request_id: str,
        source: dict[str, Any],
        extracted: dict[str, Any],
    ) -> Path:
        record_dir = self._record_dir("processed", request_id)
        record_dir.mkdir(parents=True, exist_ok=True)
        extracted_record = IngestExtractedRecord(
            request_id=request_id,
            source=source,
            extracted=extracted,
        )
        (record_dir / "source.json").write_text(
            IngestSourceRecord(request_id=request_id, source=source).to_json_text() + "\n",
            encoding="utf-8",
        )
        (record_dir / "extracted.json").write_text(
            extracted_record.to_json_text() + "\n",
            encoding="utf-8",
        )
        self._upsert_index(
            request_id=request_id,
            record_dir=record_dir,
            source=source,
            proposal=extracted,
        )
        return record_dir

    def write_composed_result(
        self,
        *,
        record_dir: Path,
        result: dict[str, Any],
    ) -> Path:
        record_dir.mkdir(parents=True, exist_ok=True)
        output_path = record_dir / "result.json"
        request_id = str(result.get("request_id") or record_dir.name)
        output_path.write_text(
            IngestComposedResultRecord.model_validate(
                {
                    "request_id": request_id,
                    "result": result,
                }
            ).to_json_text()
            + "\n",
            encoding="utf-8",
        )
        self._upsert_index(
            request_id=request_id,
            record_dir=record_dir,
            source={},
            proposal=result,
        )
        return output_path

    def write_rejected(
        self,
        *,
        request_id: str,
        source: dict[str, Any],
        error_summary: dict[str, Any],
    ) -> Path:
        record_dir = self._record_dir("rejected", request_id)
        record_dir.mkdir(parents=True, exist_ok=True)
        rejected_record = IngestRejectedRecord(
            request_id=request_id,
            source=source,
            error_summary=error_summary,
        )
        (record_dir / "source.json").write_text(
            IngestSourceRecord(request_id=request_id, source=source).to_json_text() + "\n",
            encoding="utf-8",
        )
        (record_dir / "error.json").write_text(
            rejected_record.to_json_text() + "\n",
            encoding="utf-8",
        )
        self._upsert_index(
            request_id=request_id,
            record_dir=record_dir,
            source=source,
            proposal=error_summary,
        )
        return record_dir

    def _record_dir(self, category: str, request_id: str) -> Path:
        now = datetime.utcnow()
        return (
            self.ingest_dir
            / category
            / f"{now.year:04d}"
            / f"{now.month:02d}"
            / f"{now.day:02d}"
            / request_id
        )

    def _upsert_index(
        self,
        *,
        request_id: str,
        record_dir: Path,
        source: dict[str, Any],
        proposal: dict[str, Any],
    ) -> None:
        if self.control_plane is None:
            return
        source_ref = dict(source.get("source_ref", source))
        extracted_invoice = dict(proposal.get("extracted_invoice", {}))
        normalized_invoice = dict(proposal.get("normalized_invoice", {}))
        purchase_invoice = dict(proposal.get("purchase_invoice", {}))
        doc_ref = dict(purchase_invoice.get("doc_ref", {}))
        self.control_plane.upsert_ingest_index(
            ingest_id=request_id,
            request_id=request_id,
            source_fingerprint=(
                source_ref.get("source_hash")
                or source_ref.get("source_fingerprint")
            ),
            supplier_hint=(
                normalized_invoice.get("supplier", {}) or extracted_invoice
            ).get("supplier_name"),
            external_invoice_reference=(
                extracted_invoice.get("supplier_invoice_ref")
                or normalized_invoice.get("bill_no")
            ),
            linked_review_id=(
                proposal.get("approval", {}) or {}
            ).get("approval_id"),
            linked_erp_doctype=None if not doc_ref else str(doc_ref.get("doctype")),
            linked_erp_name=None if not doc_ref else str(doc_ref.get("name")),
            record_dir=str(record_dir),
        )
