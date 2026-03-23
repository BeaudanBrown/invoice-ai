from __future__ import annotations

from typing import Any

from ..erp.schemas import ToolResponse


def conversation_state_for(*, request_kind: str, response: ToolResponse) -> dict[str, Any]:
    if request_kind not in {"quote_draft", "quote_revision"}:
        return {}

    data = response.data
    if "draft_key" not in data:
        return {}

    active_quote = {
        "draft_key": data.get("draft_key"),
        "quotation": data.get("quotation"),
        "latest_revision_id": None,
        "preview_path": None,
    }

    revision = data.get("revision")
    if isinstance(revision, dict):
        active_quote["latest_revision_id"] = revision.get("revision_id")
        active_quote["preview_path"] = revision.get("preview_path")

    preview = data.get("preview")
    if isinstance(preview, dict) and preview.get("path"):
        active_quote["preview_path"] = preview["path"]

    return {"active_quote": active_quote}


def next_request_contract(*, request_kind: str, response: ToolResponse) -> dict[str, Any]:
    if response.status != "success":
        return {}

    if request_kind == "quote_draft":
        state = conversation_state_for(request_kind=request_kind, response=response)
        return {
            "contract_version": "structured-v1",
            "planner_transition": (
                "A later chat-planner may translate free-form operator turns into this "
                "structured quote_revision envelope while reusing conversation_context.active_quote."
            ),
            "supported_follow_up": {
                "request_kind": "quote_revision",
                "conversation_context": state,
                "payload_shape": {
                    "patch": {
                        "items": [],
                        "replace_items": False,
                        "notes_append": [],
                    },
                    "summary": "Describe the revision being applied",
                },
            },
        }

    if request_kind == "quote_revision":
        return {
            "contract_version": "structured-v1",
            "planner_transition": (
                "Keep routing follow-up quote edits through quote_revision while the planner "
                "layer remains responsible only for turning chat into safe patch payloads."
            ),
        }

    return {
        "contract_version": "structured-v1",
        "planner_transition": (
            "Raw chat planning should terminate in an explicit operator request envelope before "
            "delegating to ingest or ERP tools."
        ),
    }
