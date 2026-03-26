from __future__ import annotations

import json
from pathlib import Path

from ..control_plane.models import ReviewStatus
from ..control_plane.store import ControlPlaneStore
from ..erp.schemas import ToolResponse
from .render import render_approval_diff, render_approval_summary


class ApprovalStore:
    def __init__(
        self,
        approvals_dir: Path,
        *,
        control_plane: ControlPlaneStore | None = None,
    ) -> None:
        self.approvals_dir = approvals_dir
        self.control_plane = control_plane

    def write(self, response: ToolResponse, *, request_id: str | None = None) -> Path:
        approval = response.approval
        if approval is None:
            raise ValueError("Cannot write approval artifacts for a response without approval")

        approval_dir = self.approvals_dir / approval.approval_id
        approval_dir.mkdir(parents=True, exist_ok=True)

        request_path = approval_dir / "request.json"
        summary_path = approval_dir / "summary.md"
        diff_path = approval_dir / "diff.json"

        request_path.write_text(response.to_json_text() + "\n", encoding="utf-8")
        summary_path.write_text(render_approval_summary(response), encoding="utf-8")
        diff_path.write_text(
            json.dumps(render_approval_diff(response), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if self.control_plane is not None:
            self.control_plane.record_review(
                review_id=approval.approval_id,
                request_id=request_id or response.request_id,
                review_kind=approval.action,
                status=ReviewStatus.PENDING,
                target=approval.target,
                target_summary=approval.summary,
                artifact_dir=str(approval_dir),
            )
            self.control_plane.record_artifact(
                parent_kind="review",
                parent_id=approval.approval_id,
                request_id=request_id or response.request_id,
                artifact_kind="summary_markdown",
                path=summary_path,
            )
            self.control_plane.record_artifact(
                parent_kind="review",
                parent_id=approval.approval_id,
                request_id=request_id or response.request_id,
                artifact_kind="request_json",
                path=request_path,
            )
            self.control_plane.record_artifact(
                parent_kind="review",
                parent_id=approval.approval_id,
                request_id=request_id or response.request_id,
                artifact_kind="diff_json",
                path=diff_path,
            )

        return approval_dir
