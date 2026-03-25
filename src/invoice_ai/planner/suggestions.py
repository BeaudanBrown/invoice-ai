from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .models import PlannerTurn


@dataclass(frozen=True)
class MemorySuggestionProposal:
    action: str
    scope: str
    subject: str | None
    slug: str | None
    note: str | None
    body: str | None
    metadata: dict[str, Any]
    rationale: str | None
    source: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "scope": self.scope,
            "subject": self.subject,
            "slug": self.slug,
            "note": self.note,
            "body": self.body,
            "metadata": self.metadata,
            "rationale": self.rationale,
            "source": self.source,
        }


def infer_memory_suggestions(
    *,
    turn: PlannerTurn,
    operator_request: dict[str, Any],
) -> list[MemorySuggestionProposal]:
    extracted = _extract_memory_instruction(turn.message)
    if extracted is None:
        return []

    note_text = extracted["instruction"]
    if not note_text:
        return []

    request_kind = str(operator_request.get("request_kind") or "")
    scope, subject = _resolve_scope_and_subject(
        turn=turn,
        operator_request=operator_request,
        explicit_scope=extracted.get("scope"),
        explicit_subject=extracted.get("subject"),
    )
    if scope is None:
        scope = "operator"

    metadata = {
        "origin_request_kind": request_kind or None,
        "captured_from": "planner",
    }
    if subject:
        metadata["subject"] = subject

    rationale = extracted.get("rationale")
    if rationale is None:
        rationale = _default_rationale_for(request_kind)

    return [
        MemorySuggestionProposal(
            action="record_note",
            scope=scope,
            subject=subject,
            slug=None,
            note=note_text,
            body=None,
            metadata=metadata,
            rationale=rationale,
            source={
                "kind": "planner_turn",
                "request_id": turn.request_id,
                "request_kind": request_kind or None,
                "message": turn.message,
            },
        )
    ]


def has_explicit_memory_instruction(message: str) -> bool:
    return _extract_memory_instruction(message) is not None


def is_memory_only_turn(message: str) -> bool:
    text = message.strip().lower()
    return text.startswith("remember ") or text.startswith("remember that ") or text.startswith(
        "note "
    ) or text.startswith("note that ") or text.startswith("save ")


def _extract_memory_instruction(message: str) -> dict[str, str] | None:
    text = message.strip()
    if not text:
        return None

    patterns = (
        r"^(?:please\s+)?remember(?:\s+that)?\s+(?P<instruction>.+)$",
        r"^(?:please\s+)?note(?:\s+that)?\s+(?P<instruction>.+)$",
        r"^(?:please\s+)?save(?:\s+that)?\s+(?P<instruction>.+)$",
        r"^(?P<prefix>.+?)\s+(?:remember|note)\s+(?P<instruction>.+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        instruction = match.groupdict().get("instruction", "").strip()
        if not instruction:
            continue
        return _normalize_instruction(instruction)
    return None


def _normalize_instruction(instruction: str) -> dict[str, str]:
    text = instruction.strip().rstrip(".")
    lowered = text.lower()

    prefixes = (
        ("this client ", "clients"),
        ("client ", "clients"),
        ("this job ", "jobs"),
        ("job ", "jobs"),
        ("this supplier ", "suppliers"),
        ("supplier ", "suppliers"),
        ("i ", "operator"),
        ("we ", "operator"),
    )
    for prefix, scope in prefixes:
        if not lowered.startswith(prefix):
            continue
        rest = text[len(prefix) :].strip()
        subject, note = _split_subject_and_note(rest)
        if scope == "operator":
            return {"scope": scope, "instruction": text}
        return {
            "scope": scope,
            "subject": subject,
            "instruction": note or rest,
        }
    return {"instruction": text}


def _split_subject_and_note(text: str) -> tuple[str | None, str | None]:
    match = re.match(
        r"(?P<subject>.+?)\s+(?P<note>(?:prefers|likes|wants|needs|gets|should|always|usually).+)$",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group("subject").strip(), match.group("note").strip()
    return None, text.strip()


def _resolve_scope_and_subject(
    *,
    turn: PlannerTurn,
    operator_request: dict[str, Any],
    explicit_scope: str | None,
    explicit_subject: str | None,
) -> tuple[str | None, str | None]:
    if explicit_scope == "operator":
        return "operator", None
    if explicit_scope in {"clients", "jobs", "suppliers"}:
        return explicit_scope, explicit_subject or _subject_from_request(
            scope=explicit_scope,
            turn=turn,
            operator_request=operator_request,
        )

    request_kind = str(operator_request.get("request_kind") or "")
    if request_kind in {"quote_draft", "quote_revision"}:
        return "clients", _subject_from_request(
            scope="clients",
            turn=turn,
            operator_request=operator_request,
        )
    if request_kind == "supplier_document_intake":
        return "suppliers", _subject_from_request(
            scope="suppliers",
            turn=turn,
            operator_request=operator_request,
        )
    return None, None


def _subject_from_request(
    *,
    scope: str,
    turn: PlannerTurn,
    operator_request: dict[str, Any],
) -> str | None:
    defaults_memory = dict(turn.defaults.get("memory", {}))
    if scope == "clients":
        quote = dict(operator_request.get("quote", {}))
        active_quote = turn.active_quote()
        return (
            quote.get("customer_name")
            or quote.get("customer")
            or active_quote.get("customer_name")
            or active_quote.get("customer")
            or defaults_memory.get("client")
        )
    if scope == "jobs":
        active_quote = turn.active_quote()
        return active_quote.get("job") or defaults_memory.get("job")
    if scope == "suppliers":
        supplier_document = dict(operator_request.get("supplier_document", {}))
        return (
            supplier_document.get("supplier_name")
            or supplier_document.get("supplier")
            or defaults_memory.get("supplier")
            or turn.conversation_context.get("supplier")
        )
    return None


def _default_rationale_for(request_kind: str) -> str:
    if request_kind == "quote_revision":
        return "Operator supplied a durable quoting preference during quote revision"
    if request_kind == "quote_draft":
        return "Operator supplied a durable quoting preference during quote drafting"
    if request_kind == "supplier_document_intake":
        return "Operator supplied an intake review note that may matter for future supplier ingestion"
    return "Operator supplied a durable instruction that may matter in future planning"
