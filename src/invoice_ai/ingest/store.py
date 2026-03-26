from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..persistence import (
    IngestComposedResultRecord,
    IngestExtractedRecord,
    IngestProcessedRecord,
    IngestRejectedRecord,
    IngestSourceRecord,
)


class IngestStore:
    def __init__(self, ingest_dir: Path) -> None:
        self.ingest_dir = ingest_dir

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
