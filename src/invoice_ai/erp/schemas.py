from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class ToolRequest:
    request_id: str
    tool_name: str
    dry_run: bool
    payload: dict[str, Any]
    conversation_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolRequest":
        return cls(
            request_id=str(payload["request_id"]),
            tool_name=str(payload["tool_name"]),
            dry_run=bool(payload.get("dry_run", False)),
            payload=dict(payload.get("payload", {})),
            conversation_context=dict(payload.get("conversation_context", {})),
        )

    @classmethod
    def from_json_text(cls, payload: str) -> "ToolRequest":
        return cls.from_dict(json.loads(payload))


@dataclass(frozen=True)
class ApprovalArtifactPaths:
    summary_markdown_path: str | None
    request_json_path: str | None
    diff_json_path: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "summary_markdown_path": self.summary_markdown_path,
            "request_json_path": self.request_json_path,
            "diff_json_path": self.diff_json_path,
        }


@dataclass(frozen=True)
class ApprovalPayload:
    approval_id: str
    action: str
    summary: str
    target: dict[str, Any]
    proposed_changes: dict[str, Any]
    artifacts: ApprovalArtifactPaths

    def as_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "action": self.action,
            "summary": self.summary,
            "target": self.target,
            "proposed_changes": self.proposed_changes,
            "artifacts": self.artifacts.as_dict(),
        }


@dataclass(frozen=True)
class ToolResponse:
    request_id: str
    tool_name: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    approval: ApprovalPayload | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "data": self.data,
            "errors": self.errors,
            "warnings": self.warnings,
            "approval": None if self.approval is None else self.approval.as_dict(),
            "meta": self.meta,
        }

    def to_json_text(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)


def approval_artifact_paths(root: Path, approval_id: str) -> ApprovalArtifactPaths:
    approval_dir = root / approval_id
    return ApprovalArtifactPaths(
        summary_markdown_path=str(approval_dir / "summary.md"),
        request_json_path=str(approval_dir / "request.json"),
        diff_json_path=str(approval_dir / "diff.json"),
    )
