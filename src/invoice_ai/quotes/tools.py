from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..artifacts.pdf import QuotePreviewRenderer
from ..config import RuntimeConfig
from ..erp.schemas import ToolRequest, ToolResponse
from ..erp.tools import ERPToolExecutor
from ..revisions.store import RevisionStore
from .context import QuoteContextBuilder
from .draft import preview_from_quotation_doc, quotation_payload_from_context
from .models import QuoteDraftRequest, QuoteRevisionRequest


class QuoteToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.erp = ERPToolExecutor.from_runtime_config(config)
        self.context_builder = QuoteContextBuilder(config=config, erp=self.erp)
        self.revisions = RevisionStore(config.paths.revisions_dir)
        self.preview_renderer = QuotePreviewRenderer(config.paths.artifacts_dir)

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "QuoteToolExecutor":
        return cls(config=config)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "quotes.prepare_context": self.prepare_context,
            "quotes.create_draft": self.create_draft,
            "quotes.revise_draft": self.revise_draft,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "quotes.unsupported_tool",
                        "message": f"Unsupported quotes tool: {request.tool_name}",
                    }
                ],
            )
        try:
            return handler(request)
        except (ValidationError, ValueError) as exc:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[{"code": "quotes.bad_request", "message": str(exc)}],
            )

    def prepare_context(self, request: ToolRequest) -> ToolResponse:
        draft_request = QuoteDraftRequest.from_payload(request.request_id, request.payload)
        context, approval_response = self.context_builder.build(draft_request)
        if approval_response is not None:
            return approval_response
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={"quote_context": context},
        )

    def create_draft(self, request: ToolRequest) -> ToolResponse:
        draft_request = QuoteDraftRequest.from_payload(request.request_id, request.payload)
        context, approval_response = self.context_builder.build(draft_request)
        if approval_response is not None:
            return approval_response
        assert context is not None

        erp_request = ToolRequest(
            request_id=request.request_id,
            tool_name="erp.create_draft_quotation",
            dry_run=request.dry_run,
            payload=quotation_payload_from_context(
                customer_name=str(context["customer"]["name"]),
                company=draft_request.company,
                currency=draft_request.currency,
                narrative=draft_request.narrative,
                line_items=list(context["line_items"]),
                source_refs=draft_request.source_refs,
            ),
            conversation_context={
                **request.conversation_context,
                "draft_key": draft_request.draft_key,
            },
        )
        create_response = self.erp.execute(erp_request)
        if create_response.status != "success":
            return create_response

        quotation_name = create_response.data["doc_ref"]["name"]
        quotation_doc = self._fetch_quotation_doc(
            request_id=request.request_id,
            quotation_name=quotation_name,
            proposed_doc=create_response.meta.get("proposed_doc"),
        )
        preview = preview_from_quotation_doc(
            draft_key=draft_request.draft_key,
            quotation_doc=quotation_doc,
        )
        preview_path = self.preview_renderer.render(preview)
        revision = self.revisions.write_quotation_revision(
            draft_key=draft_request.draft_key,
            quotation=quotation_name,
            revision_type="create",
            summary=draft_request.narrative.get("intro") or "Quote draft created",
            request_payload=draft_request.as_dict(),
            context=context,
            quotation_doc=quotation_doc,
            preview_path=preview_path,
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "draft_key": draft_request.draft_key,
                "quotation": quotation_name,
                "quote_context": context,
                "quotation_doc": quotation_doc,
                "preview": {
                    "path": str(preview_path),
                    "total": round(preview.total, 2),
                    "currency": preview.currency,
                },
                "revision": revision,
                "erp_request": erp_request.payload,
            },
            warnings=create_response.warnings,
            meta=create_response.meta,
        )

    def revise_draft(self, request: ToolRequest) -> ToolResponse:
        revision_request = QuoteRevisionRequest.from_payload(request.request_id, request.payload)
        latest = self.revisions.load_latest_quotation_revision(revision_request.draft_key)
        quotation_name = revision_request.quotation or latest.get("quotation")
        if not quotation_name:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[
                    {
                        "code": "quotes.missing_quotation",
                        "message": "No quotation reference available for revision",
                    }
                ],
            )

        erp_request = ToolRequest(
            request_id=request.request_id,
            tool_name="erp.update_draft_quotation",
            dry_run=request.dry_run,
            payload={
                "quotation": quotation_name,
                "patch": revision_request.patch,
            },
            conversation_context={
                **request.conversation_context,
                "draft_key": revision_request.draft_key,
            },
        )
        update_response = self.erp.execute(erp_request)
        if update_response.status != "success":
            return update_response

        quotation_doc = self._fetch_quotation_doc(
            request_id=request.request_id,
            quotation_name=quotation_name,
            proposed_doc=update_response.meta.get("proposed_doc"),
        )
        preview = preview_from_quotation_doc(
            draft_key=revision_request.draft_key,
            quotation_doc=quotation_doc,
        )
        preview_path = self.preview_renderer.render(preview)
        revision = self.revisions.write_quotation_revision(
            draft_key=revision_request.draft_key,
            quotation=quotation_name,
            revision_type="update",
            summary=revision_request.summary,
            request_payload=revision_request.as_dict(),
            context={"latest_previous_revision": latest},
            quotation_doc=quotation_doc,
            preview_path=preview_path,
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "draft_key": revision_request.draft_key,
                "quotation": quotation_name,
                "quotation_doc": quotation_doc,
                "preview": {
                    "path": str(preview_path),
                    "total": round(preview.total, 2),
                    "currency": preview.currency,
                },
                "revision": revision,
                "erp_request": erp_request.payload,
            },
            warnings=update_response.warnings,
            meta=update_response.meta,
        )

    def _fetch_quotation_doc(
        self,
        *,
        request_id: str,
        quotation_name: str | None,
        proposed_doc: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if quotation_name is None:
            return dict(proposed_doc or {})
        response = self.erp.execute(
            ToolRequest(
                request_id=f"{request_id}-fetch-quotation",
                tool_name="erp.get_doc",
                dry_run=False,
                payload={"doctype": "Quotation", "name": quotation_name},
            )
        )
        if response.status == "success":
            return dict(response.data.get("doc", {}))
        return dict(proposed_doc or {})
