from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any
import json

from pydantic import Field

from ..modeling import InvoiceAIModel


class ToolExecutionStatus(StrEnum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    VALIDATION_ERROR = "validation_error"
    APPROVAL_REQUIRED = "approval_required"
    NOT_FOUND = "not_found"


class ApprovalArtifactPaths(InvoiceAIModel):
    summary_markdown_path: str | None = None
    request_json_path: str | None = None
    diff_json_path: str | None = None


class ToolError(InvoiceAIModel):
    code: str
    message: str
    status_code: int | None = None
    details: dict[str, Any] | None = None


class ApprovalPayload(InvoiceAIModel):
    approval_id: str
    action: str
    summary: str
    target: dict[str, Any] = Field(default_factory=dict)
    proposed_changes: dict[str, Any] = Field(default_factory=dict)
    artifacts: ApprovalArtifactPaths


class ToolRequest(InvoiceAIModel):
    request_id: str
    tool_name: str
    dry_run: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    conversation_context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ToolRequest":
        return cls.model_validate(payload)

    @classmethod
    def from_json_text(cls, payload: str) -> "ToolRequest":
        parsed = json.loads(payload)
        if not isinstance(parsed, dict):
            raise ValueError("Tool request JSON must decode to an object")
        return cls.from_dict(parsed)


class ToolResponse(InvoiceAIModel):
    request_id: str
    tool_name: str
    status: ToolExecutionStatus
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[ToolError] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    approval: ApprovalPayload | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


def approval_artifact_paths(root: Path, approval_id: str) -> ApprovalArtifactPaths:
    approval_dir = root / approval_id
    return ApprovalArtifactPaths(
        summary_markdown_path=str(approval_dir / "summary.md"),
        request_json_path=str(approval_dir / "request.json"),
        diff_json_path=str(approval_dir / "diff.json"),
    )
