from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from ..modeling import InvoiceAIModel


class PlannerAttachment(InvoiceAIModel):
    kind: str = "reference"
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlannerAttachment":
        kind = str(payload.get("kind") or "reference").strip() or "reference"
        cleaned = dict(payload)
        cleaned.pop("kind", None)
        return cls(kind=kind, payload=cleaned)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, **self.payload}


class PlannerTurn(InvoiceAIModel):
    request_id: str
    message: str
    attachments: tuple[PlannerAttachment, ...] = Field(default_factory=tuple)
    defaults: dict[str, Any] = Field(default_factory=dict)
    conversation_context: dict[str, Any] = Field(default_factory=dict)

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
        return cls(
            request_id=request_id,
            message=str(payload.get("message") or payload.get("operator_message") or ""),
            attachments=attachments,
            defaults=dict(payload.get("defaults", {})),
            conversation_context=dict(conversation_context or {}),
        )

    @model_validator(mode="after")
    def _ensure_message(self) -> "PlannerTurn":
        if not self.message.strip():
            raise ValueError("Planner turn requires a non-empty message")
        return self

    def active_quote(self) -> dict[str, Any]:
        active = self.conversation_context.get("active_quote")
        if isinstance(active, dict):
            return dict(active)
        return {}
