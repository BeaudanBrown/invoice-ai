from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _looks_like_supplier_document(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in ("supplier_document", "document_path", "raw_text", "source_path", "file_name")
    )


def _looks_like_quote_request(payload: dict[str, Any]) -> bool:
    return any(
        key in payload
        for key in ("quote", "customer", "customer_name", "line_items", "items", "draft_key")
    )


@dataclass(frozen=True)
class OperatorRequest:
    request_id: str
    request_kind: str
    operator_message: str | None
    payload: dict[str, Any]

    @classmethod
    def from_payload(cls, request_id: str, payload: dict[str, Any]) -> "OperatorRequest":
        request_kind = str(payload.get("request_kind") or payload.get("kind") or "").strip()
        if not request_kind:
            if _looks_like_supplier_document(payload):
                request_kind = "supplier_document_intake"
            elif _looks_like_quote_request(payload):
                request_kind = "quote_draft"
            else:
                raise ValueError(
                    "Could not infer orchestrator request kind; provide request_kind explicitly"
                )

        normalized_kind = request_kind.replace("-", "_")
        if normalized_kind not in {"supplier_document_intake", "quote_draft"}:
            raise ValueError(f"Unsupported orchestrator request kind: {request_kind}")

        return cls(
            request_id=request_id,
            request_kind=normalized_kind,
            operator_message=_optional_string(payload.get("operator_message"))
            or _optional_string(payload.get("message")),
            payload=dict(payload),
        )

    def delegated_tool_name(self) -> str:
        if self.request_kind == "supplier_document_intake":
            return "ingest.process_supplier_document"
        return "quotes.create_draft"

    def delegated_payload(self) -> dict[str, Any]:
        if self.request_kind == "supplier_document_intake":
            nested = self.payload.get("supplier_document")
            if isinstance(nested, dict):
                return dict(nested)
            payload = dict(self.payload)
            payload.pop("request_kind", None)
            payload.pop("kind", None)
            payload.pop("operator_message", None)
            payload.pop("message", None)
            return payload

        nested = self.payload.get("quote")
        if isinstance(nested, dict):
            payload = dict(nested)
        else:
            payload = dict(self.payload)
            payload.pop("request_kind", None)
            payload.pop("kind", None)
            payload.pop("operator_message", None)
            payload.pop("message", None)
        if "draft_key" not in payload:
            payload["draft_key"] = self.request_id
        return payload


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
