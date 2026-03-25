from __future__ import annotations

from ..config import RuntimeConfig
from ..erp.schemas import ToolRequest, ToolResponse
from .store import MemoryStore


class MemoryToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.store = MemoryStore(config.paths.memory_dir)

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "MemoryToolExecutor":
        return cls(config=config)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "memory.list_documents": self.list_documents,
            "memory.get_document": self.get_document,
            "memory.upsert_document": self.upsert_document,
            "memory.record_note": self.record_note,
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
