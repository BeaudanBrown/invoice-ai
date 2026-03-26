from __future__ import annotations

from ..control_plane.store import ControlPlaneStore
from ..erp.schemas import ApprovalPayload, ToolRequest, ToolResponse, approval_artifact_paths
from ..config import RuntimeConfig
from .store import MemoryStore


class MemoryToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.store = MemoryStore(
            config.paths.memory_dir,
            control_plane=ControlPlaneStore.from_runtime_config(config),
        )

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "MemoryToolExecutor":
        return cls(config=config)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "memory.list_documents": self.list_documents,
            "memory.get_document": self.get_document,
            "memory.upsert_document": self.upsert_document,
            "memory.record_note": self.record_note,
            "memory.list_reviews": self.list_reviews,
            "memory.get_review": self.get_review,
            "memory.list_suggestions": self.list_suggestions,
            "memory.get_suggestion": self.get_suggestion,
            "memory.suggest_update": self.suggest_update,
            "memory.accept_suggestion": self.accept_suggestion,
            "memory.reject_suggestion": self.reject_suggestion,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "memory.unsupported_tool",
                        "message": f"Unsupported memory tool: {request.tool_name}",
                    }
                ],
            )
        try:
            return handler(request)
        except ValueError as exc:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[{"code": "memory.bad_request", "message": str(exc)}],
            )

    def list_documents(self, request: ToolRequest) -> ToolResponse:
        scope = request.payload.get("scope")
        documents = self.store.list_documents(scope=None if scope is None else str(scope))
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"documents": [document.as_context() for document in documents]},
        )

    def get_document(self, request: ToolRequest) -> ToolResponse:
        scope = str(request.payload["scope"])
        slug = str(request.payload["slug"])
        document = self.store.get_document(scope=scope, slug=slug)
        if document is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="not_found",
                errors=[
                    {
                        "code": "memory.not_found",
                        "message": f"No memory document found for {scope}/{slug}",
                    }
                ],
            )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"document": document.as_context()},
        )

    def upsert_document(self, request: ToolRequest) -> ToolResponse:
        document = self.store.upsert_document(
            scope=str(request.payload["scope"]),
            slug=None if request.payload.get("slug") is None else str(request.payload["slug"]),
            subject=None
            if request.payload.get("subject") is None
            else str(request.payload["subject"]),
            metadata=dict(request.payload.get("metadata", {})),
            body=None if request.payload.get("body") is None else str(request.payload["body"]),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"document": document.as_context()},
        )

    def record_note(self, request: ToolRequest) -> ToolResponse:
        document = self.store.record_note(
            scope=str(request.payload["scope"]),
            slug=None if request.payload.get("slug") is None else str(request.payload["slug"]),
            subject=None
            if request.payload.get("subject") is None
            else str(request.payload["subject"]),
            note=str(request.payload["note"]),
            metadata=dict(request.payload.get("metadata", {})),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"document": document.as_context()},
        )

    def list_reviews(self, request: ToolRequest) -> ToolResponse:
        status = request.payload.get("status", "pending")
        scope = request.payload.get("scope")
        suggestions = self.store.list_suggestions(
            status=None if status is None else str(status),
            scope=None if scope is None else str(scope),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"reviews": [self._review_entry(suggestion) for suggestion in suggestions]},
        )

    def get_review(self, request: ToolRequest) -> ToolResponse:
        suggestion = self.store.get_suggestion(
            suggestion_id=str(request.payload["suggestion_id"])
        )
        if suggestion is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="not_found",
                errors=[
                    {
                        "code": "memory.review_not_found",
                        "message": (
                            "No memory review found for "
                            f"{request.payload['suggestion_id']}"
                        ),
                    }
                ],
            )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"review": self._review_entry(suggestion)},
        )

    def list_suggestions(self, request: ToolRequest) -> ToolResponse:
        status = request.payload.get("status")
        scope = request.payload.get("scope")
        suggestions = self.store.list_suggestions(
            status=None if status is None else str(status),
            scope=None if scope is None else str(scope),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"suggestions": [suggestion.as_context() for suggestion in suggestions]},
        )

    def get_suggestion(self, request: ToolRequest) -> ToolResponse:
        suggestion = self.store.get_suggestion(
            suggestion_id=str(request.payload["suggestion_id"])
        )
        if suggestion is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="not_found",
                errors=[
                    {
                        "code": "memory.suggestion_not_found",
                        "message": (
                            "No memory suggestion found for "
                            f"{request.payload['suggestion_id']}"
                        ),
                    }
                ],
            )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"suggestion": suggestion.as_context()},
        )

    def suggest_update(self, request: ToolRequest) -> ToolResponse:
        suggestion = self.store.suggest_update(
            action=str(request.payload["action"]),
            scope=str(request.payload["scope"]),
            slug=None if request.payload.get("slug") is None else str(request.payload["slug"]),
            subject=None
            if request.payload.get("subject") is None
            else str(request.payload["subject"]),
            metadata=dict(request.payload.get("metadata", {})),
            body=None if request.payload.get("body") is None else str(request.payload["body"]),
            note=None if request.payload.get("note") is None else str(request.payload["note"]),
            rationale=(
                None
                if request.payload.get("rationale") is None
                else str(request.payload["rationale"])
            ),
            source=dict(request.payload.get("source", {})),
        )
        approval = ApprovalPayload(
            approval_id=suggestion.suggestion_id,
            action=f"memory.{suggestion.action}",
            summary=(
                f"Review memory suggestion for {suggestion.scope}/{suggestion.slug}"
            ),
            target={
                "doctype": "MemoryDocument",
                "name": f"{suggestion.scope}/{suggestion.slug}",
                "scope": suggestion.scope,
                "slug": suggestion.slug,
            },
            proposed_changes={
                "action": suggestion.action,
                "metadata": suggestion.metadata,
                "body": suggestion.body,
                "note": suggestion.note,
                "rationale": suggestion.rationale,
                "source": suggestion.source,
            },
            artifacts=approval_artifact_paths(
                self.config.paths.approvals_dir, suggestion.suggestion_id
            ),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="approval_required",
            data={"suggestion": suggestion.as_context()},
            approval=approval,
        )

    def accept_suggestion(self, request: ToolRequest) -> ToolResponse:
        suggestion, document = self.store.accept_suggestion(
            suggestion_id=str(request.payload["suggestion_id"]),
            reviewer=(
                None
                if request.payload.get("reviewer") is None
                else str(request.payload["reviewer"])
            ),
            decision_note=(
                None
                if request.payload.get("decision_note") is None
                else str(request.payload["decision_note"])
            ),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "suggestion": suggestion.as_context(),
                "document": document.as_context(),
            },
        )

    def reject_suggestion(self, request: ToolRequest) -> ToolResponse:
        suggestion = self.store.reject_suggestion(
            suggestion_id=str(request.payload["suggestion_id"]),
            reviewer=(
                None
                if request.payload.get("reviewer") is None
                else str(request.payload["reviewer"])
            ),
            decision_note=(
                None
                if request.payload.get("decision_note") is None
                else str(request.payload["decision_note"])
            ),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"suggestion": suggestion.as_context()},
        )

    def _review_entry(self, suggestion) -> dict[str, object]:
        artifacts = approval_artifact_paths(
            self.config.paths.approvals_dir,
            suggestion.suggestion_id,
        )
        paths = artifacts.as_dict()
        existing_artifacts = {
            key: value
            for key, value in paths.items()
            if value is not None and self._path_exists(value)
        }
        summary_preview = None
        summary_path = paths.get("summary_markdown_path")
        if summary_path is not None and self._path_exists(summary_path):
            summary_preview = self._summary_preview(summary_path)

        return {
            "suggestion_id": suggestion.suggestion_id,
            "status": suggestion.status,
            "scope": suggestion.scope,
            "slug": suggestion.slug,
            "subject": suggestion.subject,
            "created_at": suggestion.created_at,
            "updated_at": suggestion.updated_at,
            "reviewed_at": suggestion.reviewed_at,
            "decision_note": suggestion.decision_note,
            "suggestion": suggestion.as_context(),
            "artifacts": paths,
            "existing_artifacts": existing_artifacts,
            "summary_preview": summary_preview,
        }

    @staticmethod
    def _path_exists(path: str) -> bool:
        from pathlib import Path

        return Path(path).exists()

    @staticmethod
    def _summary_preview(path: str) -> str:
        from pathlib import Path

        lines = Path(path).read_text(encoding="utf-8").splitlines()
        preview = [line for line in lines if line.strip()][:3]
        return "\n".join(preview)
