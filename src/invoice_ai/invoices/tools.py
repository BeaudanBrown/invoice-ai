from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..artifacts.pdf import SalesInvoicePreviewRenderer
from ..config import RuntimeConfig
from ..control_plane.store import ControlPlaneStore
from ..erp.schemas import ToolRequest, ToolResponse
from ..erp.tools import ERPToolExecutor
from ..revisions.store import RevisionStore
from .context import InvoiceContextBuilder
from .draft import preview_from_sales_invoice_doc, sales_invoice_payload_from_context
from .models import InvoiceDraftRequest, InvoiceRevisionRequest


class InvoiceToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.erp = ERPToolExecutor.from_runtime_config(config)
        self.context_builder = InvoiceContextBuilder(config=config, erp=self.erp)
        self.revisions = RevisionStore(
            config.paths.revisions_dir,
            control_plane=ControlPlaneStore.from_runtime_config(config),
        )
        self.preview_renderer = SalesInvoicePreviewRenderer(config.paths.artifacts_dir)

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "InvoiceToolExecutor":
        return cls(config=config)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "invoices.create_draft": self.create_draft,
            "invoices.revise_draft": self.revise_draft,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "invoices.unsupported_tool",
                        "message": f"Unsupported invoices tool: {request.tool_name}",
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
                errors=[{"code": "invoices.bad_request", "message": str(exc)}],
            )

    def create_draft(self, request: ToolRequest) -> ToolResponse:
        draft_request = InvoiceDraftRequest.from_payload(request.request_id, request.payload)
        context, approval_response = self.context_builder.build(draft_request)
        if approval_response is not None:
            return approval_response
        assert context is not None

        erp_request = ToolRequest(
            request_id=request.request_id,
            tool_name="erp.create_draft_sales_invoice",
            dry_run=request.dry_run,
            payload=sales_invoice_payload_from_context(
                customer_name=str(context["customer"]["name"]),
                company=draft_request.company,
                currency=draft_request.currency,
                narrative=draft_request.narrative,
                line_items=list(context["line_items"]),
                source_refs=draft_request.source_refs,
                source_quotation=context.get("source_quotation"),
            ),
            conversation_context={
                **request.conversation_context,
                "draft_key": draft_request.draft_key,
            },
        )
        create_response = self.erp.execute(erp_request)
        if create_response.status != "success":
            return create_response

        sales_invoice_name = create_response.data["doc_ref"]["name"]
        sales_invoice_doc = self._fetch_sales_invoice_doc(
            request_id=request.request_id,
            sales_invoice_name=sales_invoice_name,
            proposed_doc=create_response.meta.get("proposed_doc"),
        )
        preview = preview_from_sales_invoice_doc(
            draft_key=draft_request.draft_key,
            sales_invoice_doc=sales_invoice_doc,
        )
        preview_path = self.preview_renderer.render(preview)
        revision = self.revisions.write_sales_invoice_revision(
            draft_key=draft_request.draft_key,
            sales_invoice=sales_invoice_name,
            source_quotation=context.get("source_quotation"),
            revision_type="create",
            summary=draft_request.narrative.get("intro") or "Sales invoice draft created",
            request_payload=draft_request.as_dict(),
            context=context,
            sales_invoice_doc=sales_invoice_doc,
            preview_path=preview_path,
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "draft_key": draft_request.draft_key,
                "sales_invoice": sales_invoice_name,
                "source_quotation": context.get("source_quotation"),
                "invoice_context": context,
                "sales_invoice_doc": sales_invoice_doc,
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
        revision_request = InvoiceRevisionRequest.from_payload(request.request_id, request.payload)
        latest = self.revisions.load_latest_sales_invoice_revision(revision_request.draft_key)
        sales_invoice_name = revision_request.sales_invoice or latest.get("sales_invoice")
        if not sales_invoice_name:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[
                    {
                        "code": "invoices.missing_sales_invoice",
                        "message": "No sales invoice reference available for revision",
                    }
                ],
            )

        erp_request = ToolRequest(
            request_id=request.request_id,
            tool_name="erp.update_draft_sales_invoice",
            dry_run=request.dry_run,
            payload={
                "sales_invoice": sales_invoice_name,
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

        sales_invoice_doc = self._fetch_sales_invoice_doc(
            request_id=request.request_id,
            sales_invoice_name=sales_invoice_name,
            proposed_doc=update_response.meta.get("proposed_doc"),
        )
        preview = preview_from_sales_invoice_doc(
            draft_key=revision_request.draft_key,
            sales_invoice_doc=sales_invoice_doc,
        )
        preview_path = self.preview_renderer.render(preview)
        revision = self.revisions.write_sales_invoice_revision(
            draft_key=revision_request.draft_key,
            sales_invoice=sales_invoice_name,
            source_quotation=latest.get("source_quotation"),
            revision_type="update",
            summary=revision_request.summary,
            request_payload=revision_request.as_dict(),
            context={"latest_previous_revision": latest},
            sales_invoice_doc=sales_invoice_doc,
            preview_path=preview_path,
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "draft_key": revision_request.draft_key,
                "sales_invoice": sales_invoice_name,
                "source_quotation": latest.get("source_quotation"),
                "sales_invoice_doc": sales_invoice_doc,
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

    def _fetch_sales_invoice_doc(
        self,
        *,
        request_id: str,
        sales_invoice_name: str | None,
        proposed_doc: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if sales_invoice_name is None:
            return dict(proposed_doc or {})
        response = self.erp.execute(
            ToolRequest(
                request_id=f"{request_id}-fetch-sales-invoice",
                tool_name="erp.get_doc",
                dry_run=False,
                payload={"doctype": "Sales Invoice", "name": sales_invoice_name},
            )
        )
        if response.status == "success":
            return dict(response.data.get("doc", {}))
        return dict(proposed_doc or {})
