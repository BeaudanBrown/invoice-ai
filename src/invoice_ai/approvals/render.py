from __future__ import annotations

from typing import Any

from ..erp.schemas import ToolResponse


def render_approval_summary(response: ToolResponse) -> str:
    approval = response.approval
    if approval is None:
        raise ValueError("Approval summary requires a response with approval data")

    lines = [
        f"# Approval Request: {approval.action}",
        "",
        f"- Approval ID: `{approval.approval_id}`",
        f"- Tool: `{response.tool_name}`",
        f"- Request ID: `{response.request_id}`",
        f"- Summary: {approval.summary}",
        f"- Target doctype: `{approval.target.get('doctype')}`",
        f"- Target name: `{approval.target.get('name')}`",
        "",
        "## Proposed Changes",
        "",
    ]

    proposed_changes = approval.proposed_changes or {}
    if proposed_changes:
        for key in sorted(proposed_changes):
            lines.append(f"- `{key}`: {proposed_changes[key]}")
    else:
        lines.append("- No structured field changes were provided.")

    if response.warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in response.warnings:
            lines.append(f"- {warning}")

    if response.errors:
        lines.extend(["", "## Errors", ""])
        for error in response.errors:
            lines.append(f"- `{error.get('code', 'error')}`: {error.get('message')}")

    return "\n".join(lines) + "\n"


def render_approval_diff(response: ToolResponse) -> dict[str, Any]:
    approval = response.approval
    if approval is None:
        raise ValueError("Approval diff requires a response with approval data")

    return {
        "action": approval.action,
        "target": approval.target,
        "proposed_changes": approval.proposed_changes,
        "warnings": response.warnings,
        "errors": response.errors,
    }
