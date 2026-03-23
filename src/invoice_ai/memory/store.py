from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


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
