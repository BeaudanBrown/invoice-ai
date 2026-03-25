from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any
import uuid


@dataclass(frozen=True)
class MemoryDocument:
    scope: str
    slug: str
    path: Path
    metadata: dict[str, Any]
    body: str

    def as_context(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "slug": self.slug,
            "path": str(self.path),
            "metadata": self.metadata,
            "body": self.body,
        }


@dataclass(frozen=True)
class MemorySuggestion:
    suggestion_id: str
    action: str
    scope: str
    slug: str
    subject: str | None
    status: str
    metadata: dict[str, Any]
    body: str | None
    note: str | None
    rationale: str | None
    source: dict[str, Any]
    created_at: str
    updated_at: str
    reviewed_at: str | None
    decision_note: str | None
    current_document: dict[str, Any] | None

    def as_context(self) -> dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "action": self.action,
            "scope": self.scope,
            "slug": self.slug,
            "subject": self.subject,
            "status": self.status,
            "metadata": self.metadata,
            "body": self.body,
            "note": self.note,
            "rationale": self.rationale,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewed_at": self.reviewed_at,
            "decision_note": self.decision_note,
            "current_document": self.current_document,
        }


class MemoryStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def planning_context(
        self,
        *,
        message: str,
        defaults: dict[str, Any],
        conversation_context: dict[str, Any],
    ) -> dict[str, Any]:
        documents = self._selected_documents(
            message=message,
            defaults=defaults,
            conversation_context=conversation_context,
        )
        return {
            "documents": [document.as_context() for document in documents],
            "merged_defaults": self._merge_defaults(defaults=defaults, documents=documents),
        }

    def list_documents(self, *, scope: str | None = None) -> list[MemoryDocument]:
        scopes = [scope] if scope is not None else ["global", "operator", "clients", "jobs"]
        documents: list[MemoryDocument] = []
        for scope_name in scopes:
            documents.extend(self._documents_in_scope(scope_name))
        return documents

    def get_document(self, *, scope: str, slug: str) -> MemoryDocument | None:
        path = self._document_path(scope=scope, slug=slug)
        if not path.exists():
            return None
        return self._load_document(scope=scope, path=path)

    def list_suggestions(
        self,
        *,
        status: str | None = None,
        scope: str | None = None,
    ) -> list[MemorySuggestion]:
        suggestions_dir = self._suggestions_dir()
        if not suggestions_dir.exists():
            return []

        selected_status = None if status is None else _validated_suggestion_status(status)
        selected_scope = None if scope is None else _validated_scope(scope)

        suggestions: list[MemorySuggestion] = []
        for path in sorted(suggestions_dir.glob("*.json")):
            suggestion = self._load_suggestion(path)
            if selected_status is not None and suggestion.status != selected_status:
                continue
            if selected_scope is not None and suggestion.scope != selected_scope:
                continue
            suggestions.append(suggestion)
        return suggestions

    def get_suggestion(self, *, suggestion_id: str) -> MemorySuggestion | None:
        path = self._suggestion_path(suggestion_id)
        if not path.exists():
            return None
        return self._load_suggestion(path)

    def upsert_document(
        self,
        *,
        scope: str,
        slug: str | None = None,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
        body: str | None = None,
    ) -> MemoryDocument:
        scope = _validated_scope(scope)
        target_slug = slug or _slugify(subject)
        if not target_slug:
            raise ValueError("Memory document requires slug or subject")

        path = self._document_path(scope=scope, slug=target_slug)
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = self.get_document(scope=scope, slug=target_slug)
        existing_metadata = {} if existing is None else dict(existing.metadata)
        merged_metadata = _deep_merge_dict(existing_metadata, metadata or {})
        merged_metadata.setdefault("subject", subject or merged_metadata.get("subject") or target_slug)
        merged_metadata["updated_at"] = datetime.utcnow().isoformat() + "Z"

        if body is None:
            rendered_body = "" if existing is None else existing.body
        else:
            rendered_body = body.strip()

        path.write_text(
            _render_document(metadata=merged_metadata, body=rendered_body),
            encoding="utf-8",
        )
        return self._load_document(scope=scope, path=path)

    def record_note(
        self,
        *,
        scope: str,
        slug: str | None = None,
        subject: str | None = None,
        note: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryDocument:
        scope = _validated_scope(scope)
        target_slug = slug or _slugify(subject)
        if not target_slug:
            raise ValueError("Memory note requires slug or subject")
        if not note.strip():
            raise ValueError("Memory note cannot be empty")

        existing = self.get_document(scope=scope, slug=target_slug)
        timestamp = datetime.utcnow().isoformat() + "Z"
        note_block = f"## Note {timestamp}\n\n{note.strip()}"
        body = note_block if existing is None or not existing.body else f"{existing.body}\n\n{note_block}"
        return self.upsert_document(
            scope=scope,
            slug=target_slug,
            subject=subject,
            metadata=metadata,
            body=body,
        )

    def suggest_update(
        self,
        *,
        action: str,
        scope: str,
        slug: str | None = None,
        subject: str | None = None,
        metadata: dict[str, Any] | None = None,
        body: str | None = None,
        note: str | None = None,
        rationale: str | None = None,
        source: dict[str, Any] | None = None,
    ) -> MemorySuggestion:
        normalized_action = _validated_suggestion_action(action)
        normalized_scope = _validated_scope(scope)
        target_slug = slug or _slugify(subject)
        if not target_slug:
            raise ValueError("Memory suggestion requires slug or subject")

        payload_metadata = dict(metadata or {})
        payload_source = dict(source or {})
        suggestion_id = f"memory-suggestion-{uuid.uuid4().hex}"
        timestamp = datetime.utcnow().isoformat() + "Z"

        if normalized_action == "upsert_document":
            if body is None or not body.strip():
                raise ValueError("Document suggestions require body content")
            suggestion_body = body.strip()
            suggestion_note = None
        else:
            if note is None or not note.strip():
                raise ValueError("Note suggestions require note content")
            suggestion_body = None
            suggestion_note = note.strip()

        current_document = self.get_document(scope=normalized_scope, slug=target_slug)
        suggestion = MemorySuggestion(
            suggestion_id=suggestion_id,
            action=normalized_action,
            scope=normalized_scope,
            slug=target_slug,
            subject=subject,
            status="pending",
            metadata=payload_metadata,
            body=suggestion_body,
            note=suggestion_note,
            rationale=None if rationale is None else rationale.strip() or None,
            source=payload_source,
            created_at=timestamp,
            updated_at=timestamp,
            reviewed_at=None,
            decision_note=None,
            current_document=(
                None if current_document is None else current_document.as_context()
            ),
        )
        self._write_suggestion(suggestion)
        return suggestion

    def accept_suggestion(
        self,
        *,
        suggestion_id: str,
        reviewer: str | None = None,
        decision_note: str | None = None,
    ) -> tuple[MemorySuggestion, MemoryDocument]:
        suggestion = self._require_pending_suggestion(suggestion_id)

        if suggestion.action == "upsert_document":
            document = self.upsert_document(
                scope=suggestion.scope,
                slug=suggestion.slug,
                subject=suggestion.subject,
                metadata=suggestion.metadata,
                body=suggestion.body,
            )
        else:
            assert suggestion.note is not None
            document = self.record_note(
                scope=suggestion.scope,
                slug=suggestion.slug,
                subject=suggestion.subject,
                note=suggestion.note,
                metadata=suggestion.metadata,
            )

        updated = self._reviewed_suggestion(
            suggestion,
            status="accepted",
            reviewer=reviewer,
            decision_note=decision_note,
        )
        self._write_suggestion(updated)
        return updated, document

    def reject_suggestion(
        self,
        *,
        suggestion_id: str,
        reviewer: str | None = None,
        decision_note: str | None = None,
    ) -> MemorySuggestion:
        suggestion = self._require_pending_suggestion(suggestion_id)
        updated = self._reviewed_suggestion(
            suggestion,
            status="rejected",
            reviewer=reviewer,
            decision_note=decision_note,
        )
        self._write_suggestion(updated)
        return updated

    def _selected_documents(
        self,
        *,
        message: str,
        defaults: dict[str, Any],
        conversation_context: dict[str, Any],
    ) -> list[MemoryDocument]:
        selected: list[MemoryDocument] = []
        selected.extend(self._documents_in_scope("global"))
        selected.extend(self._documents_in_scope("operator"))

        selectors = dict(defaults.get("memory", {}))
        quote_defaults = dict(defaults.get("quote", {}))
        active_quote = dict(conversation_context.get("active_quote", {}))

        client_candidates = [
            selectors.get("client"),
            quote_defaults.get("customer"),
            quote_defaults.get("customer_name"),
            active_quote.get("customer"),
            _extract_customer_candidate(message),
        ]
        job_candidates = [
            selectors.get("job"),
            quote_defaults.get("job"),
            active_quote.get("job"),
        ]

        client_documents = self._documents_for_scope_and_candidates("clients", client_candidates)
        job_documents = self._documents_for_scope_and_candidates("jobs", job_candidates)
        selected.extend(client_documents)
        selected.extend(job_documents)

        deduped: list[MemoryDocument] = []
        seen: set[str] = set()
        for document in selected:
            key = str(document.path)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(document)
        return deduped

    def _documents_in_scope(self, scope: str) -> list[MemoryDocument]:
        scope_dir = self.root / scope
        if not scope_dir.exists():
            return []
        documents: list[MemoryDocument] = []
        for path in sorted(scope_dir.glob("*.md")):
            documents.append(self._load_document(scope=scope, path=path))
        return documents

    def _documents_for_scope_and_candidates(
        self,
        scope: str,
        candidates: list[Any],
    ) -> list[MemoryDocument]:
        scope_dir = self.root / scope
        if not scope_dir.exists():
            return []

        normalized_candidates = {
            _slugify(candidate)
            for candidate in candidates
            if isinstance(candidate, str) and candidate.strip()
        }
        if not normalized_candidates:
            return []

        documents: list[MemoryDocument] = []
        for path in sorted(scope_dir.glob("*.md")):
            document = self._load_document(scope=scope, path=path)
            keys = {
                document.slug,
                _slugify(document.metadata.get("subject")),
                _slugify(document.metadata.get("customer")),
                _slugify(document.metadata.get("customer_name")),
                _slugify(document.metadata.get("canonical_customer")),
                _slugify(document.metadata.get("job")),
            }
            if normalized_candidates.intersection({key for key in keys if key}):
                documents.append(document)
        return documents

    def _load_suggestion(self, path: Path) -> MemorySuggestion:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return MemorySuggestion(
            suggestion_id=str(payload["suggestion_id"]),
            action=str(payload["action"]),
            scope=str(payload["scope"]),
            slug=str(payload["slug"]),
            subject=None if payload.get("subject") is None else str(payload["subject"]),
            status=str(payload["status"]),
            metadata=dict(payload.get("metadata", {})),
            body=None if payload.get("body") is None else str(payload["body"]),
            note=None if payload.get("note") is None else str(payload["note"]),
            rationale=(
                None if payload.get("rationale") is None else str(payload["rationale"])
            ),
            source=dict(payload.get("source", {})),
            created_at=str(payload["created_at"]),
            updated_at=str(payload["updated_at"]),
            reviewed_at=(
                None if payload.get("reviewed_at") is None else str(payload["reviewed_at"])
            ),
            decision_note=(
                None
                if payload.get("decision_note") is None
                else str(payload["decision_note"])
            ),
            current_document=payload.get("current_document"),
        )

    def _load_document(self, *, scope: str, path: Path) -> MemoryDocument:
        raw = path.read_text(encoding="utf-8")
        metadata, body = _split_frontmatter(raw)
        return MemoryDocument(
            scope=scope,
            slug=path.stem,
            path=path,
            metadata=metadata,
            body=body.strip(),
        )

    def _document_path(self, *, scope: str, slug: str) -> Path:
        return self.root / scope / f"{_slugify(slug)}.md"

    def _suggestions_dir(self) -> Path:
        return self.root / "_suggestions"

    def _suggestion_path(self, suggestion_id: str) -> Path:
        return self._suggestions_dir() / f"{_slugify(suggestion_id)}.json"

    def _write_suggestion(self, suggestion: MemorySuggestion) -> None:
        path = self._suggestion_path(suggestion.suggestion_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(suggestion.as_context(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _require_pending_suggestion(self, suggestion_id: str) -> MemorySuggestion:
        suggestion = self.get_suggestion(suggestion_id=suggestion_id)
        if suggestion is None:
            raise ValueError(f"Unknown memory suggestion: {suggestion_id}")
        if suggestion.status != "pending":
            raise ValueError(
                f"Memory suggestion {suggestion_id} is already {suggestion.status}"
            )
        return suggestion

    def _reviewed_suggestion(
        self,
        suggestion: MemorySuggestion,
        *,
        status: str,
        reviewer: str | None,
        decision_note: str | None,
    ) -> MemorySuggestion:
        timestamp = datetime.utcnow().isoformat() + "Z"
        metadata = dict(suggestion.metadata)
        if reviewer:
            metadata.setdefault("review", {})
            if isinstance(metadata["review"], dict):
                metadata["review"] = dict(metadata["review"])
                metadata["review"]["reviewer"] = reviewer
        return MemorySuggestion(
            suggestion_id=suggestion.suggestion_id,
            action=suggestion.action,
            scope=suggestion.scope,
            slug=suggestion.slug,
            subject=suggestion.subject,
            status=status,
            metadata=metadata,
            body=suggestion.body,
            note=suggestion.note,
            rationale=suggestion.rationale,
            source=suggestion.source,
            created_at=suggestion.created_at,
            updated_at=timestamp,
            reviewed_at=timestamp,
            decision_note=None if decision_note is None else decision_note.strip() or None,
            current_document=suggestion.current_document,
        )

    def _merge_defaults(
        self,
        *,
        defaults: dict[str, Any],
        documents: list[MemoryDocument],
    ) -> dict[str, Any]:
        merged = json.loads(json.dumps(defaults))
        quote_defaults = dict(merged.get("quote", {}))
        memory_defaults = dict(merged.get("memory", {}))

        for document in documents:
            metadata = document.metadata
            quote_override = metadata.get("quote_defaults")
            if isinstance(quote_override, dict):
                quote_defaults = _deep_merge_dict(quote_defaults, quote_override)

            for key in (
                "customer",
                "customer_name",
                "canonical_customer",
                "labor_item_code",
                "labor_item_name",
                "labor_description",
                "travel_item_code",
                "travel_item_name",
                "travel_description",
                "travel_rate",
                "intro",
                "notes",
            ):
                if key not in metadata:
                    continue
                target_key = "customer" if key == "canonical_customer" else key
                quote_defaults.setdefault(target_key, metadata[key])

            if document.scope == "clients":
                memory_defaults.setdefault("client", metadata.get("subject") or document.slug)
            if document.scope == "jobs":
                memory_defaults.setdefault("job", metadata.get("subject") or document.slug)

        if quote_defaults:
            merged["quote"] = quote_defaults
        if memory_defaults:
            merged["memory"] = memory_defaults
        return merged


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    _, rest = raw.split("---\n", 1)
    if "\n---\n" not in rest:
        return {}, raw
    frontmatter, body = rest.split("\n---\n", 1)
    metadata: dict[str, Any] = {}
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = _parse_frontmatter_value(value.strip())
    return metadata, body


def _parse_frontmatter_value(value: str) -> Any:
    if not value:
        return ""
    if value.startswith("{") or value.startswith("["):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    if "," in value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _slugify(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _extract_customer_candidate(message: str) -> str | None:
    match = re.search(r"\bquote\s+(.+?)\s+for\b", message, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _deep_merge_dict(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _render_document(*, metadata: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key in sorted(metadata):
        lines.append(f"{key}: {_render_frontmatter_value(metadata[key])}")
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def _render_frontmatter_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _validated_scope(scope: str) -> str:
    normalized = scope.strip().lower()
    if normalized not in {"global", "operator", "clients", "jobs"}:
        raise ValueError(f"Unsupported memory scope: {scope}")
    return normalized


def _validated_suggestion_action(action: str) -> str:
    normalized = action.strip().lower()
    if normalized not in {"upsert_document", "record_note"}:
        raise ValueError(f"Unsupported memory suggestion action: {action}")
    return normalized


def _validated_suggestion_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in {"pending", "accepted", "rejected"}:
        raise ValueError(f"Unsupported memory suggestion status: {status}")
    return normalized
