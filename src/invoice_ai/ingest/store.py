from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


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
        (record_dir / "source.json").write_text(
            json.dumps(source, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (record_dir / "proposal.json").write_text(
            json.dumps(normalized, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
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
        (record_dir / "source.json").write_text(
            json.dumps(source, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (record_dir / "extracted.json").write_text(
            json.dumps(extracted, indent=2, sort_keys=True) + "\n",
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
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
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
        (record_dir / "source.json").write_text(
            json.dumps(source, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (record_dir / "error.json").write_text(
            json.dumps(error_summary, indent=2, sort_keys=True) + "\n",
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
