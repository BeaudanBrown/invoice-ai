from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True)
class PlannerAttachment:
    kind: str
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlannerAttachment":
        kind = _optional_string(payload.get("kind")) or "reference"
        cleaned = dict(payload)
        cleaned.pop("kind", None)
        return cls(kind=kind, payload=cleaned)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, **self.payload}


@dataclass(frozen=True)
class PlannerTurn:
    request_id: str
    message: str
    attachments: tuple[PlannerAttachment, ...] = field(default_factory=tuple)
    defaults: dict[str, Any] = field(default_factory=dict)
    conversation_context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls,
        request_id: str,
        payload: dict[str, Any],
        *,
        conversation_context: dict[str, Any] | None = None,
    ) -> "PlannerTurn":
        attachments = tuple(
            PlannerAttachment.from_dict(item) for item in payload.get("attachments", [])
        )
        defaults = dict(payload.get("defaults", {}))
        return cls(
            request_id=request_id,
            message=str(payload.get("message") or payload.get("operator_message") or ""),
            attachments=attachments,
            defaults=defaults,
            conversation_context=dict(conversation_context or {}),
        )

    def active_quote(self) -> dict[str, Any]:
        active = self.conversation_context.get("active_quote")
        if isinstance(active, dict):
            return dict(active)
        return {}
