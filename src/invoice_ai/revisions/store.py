from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..persistence import LatestQuotationRevisionRecord, QuotationRevisionRecord


class RevisionStore:
    def __init__(self, revisions_dir: Path) -> None:
        self.revisions_dir = revisions_dir

    def write_quotation_revision(
        self,
        *,
        draft_key: str,
        quotation: str | None,
        revision_type: str,
        summary: str,
        request_payload: dict[str, Any],
        context: dict[str, Any],
        quotation_doc: dict[str, Any],
        preview_path: Path | None,
    ) -> dict[str, Any]:
        target_dir = self.revisions_dir / "quotations" / draft_key
        target_dir.mkdir(parents=True, exist_ok=True)

        existing = sorted(target_dir.glob("revision-*.json"))
        revision_number = len(existing) + 1
        revision_id = f"revision-{revision_number:04d}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        payload = QuotationRevisionRecord(
            revision_id=revision_id,
            revision_number=revision_number,
            draft_key=draft_key,
            quotation=quotation,
            revision_type=revision_type,
            summary=summary,
            created_at=timestamp,
            request_payload=request_payload,
            context=context,
            quotation_doc=quotation_doc,
            preview_path=None if preview_path is None else str(preview_path),
        )

        revision_path = target_dir / f"{revision_id}.json"
        revision_path.write_text(payload.to_json_text() + "\n", encoding="utf-8")

        latest_path = target_dir / "latest.json"
        latest_path.write_text(
            LatestQuotationRevisionRecord(
                draft_key=draft_key,
                quotation=quotation,
                latest_revision_id=revision_id,
                latest_revision_number=revision_number,
                updated_at=timestamp,
                latest_revision_path=str(revision_path),
                preview_path=None if preview_path is None else str(preview_path),
            ).to_json_text()
            + "\n",
            encoding="utf-8",
        )
        return payload.as_dict()

    def load_latest_quotation_revision(self, draft_key: str) -> dict[str, Any]:
        latest_path = self.revisions_dir / "quotations" / draft_key / "latest.json"
        if not latest_path.exists():
            raise FileNotFoundError(f"No stored quotation revisions for draft key {draft_key}")
        return LatestQuotationRevisionRecord.model_validate_json(
            latest_path.read_text(encoding="utf-8")
        ).as_dict()
