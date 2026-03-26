from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid

from ..config import RuntimeConfig
from .client import ERPNextClient, ERPNextClientError
from .commands import (
    AttachFileCommand,
    CreateDraftPurchaseInvoiceCommand,
    CreateDraftQuotationCommand,
    GetDocCommand,
    LinkedContextCommand,
    ListDocsCommand,
    PricingContextCommand,
    UpdateDraftQuotationCommand,
)
from .schemas import (
    ApprovalPayload,
    ToolError,
    ToolExecutionStatus,
    ToolRequest,
    ToolResponse,
    approval_artifact_paths,
)


@dataclass
class ERPToolExecutor:
    config: RuntimeConfig
    client: ERPNextClient

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "ERPToolExecutor":
        return cls(config=config, client=ERPNextClient.from_runtime_config(config))

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "erp.get_doc": self.get_doc,
            "erp.list_docs": self.list_docs,
            "erp.get_linked_context": self.get_linked_context,
            "erp.get_pricing_context": self.get_pricing_context,
            "erp.create_draft_quotation": self.create_draft_quotation,
            "erp.update_draft_quotation": self.update_draft_quotation,
            "erp.create_draft_purchase_invoice": self.create_draft_purchase_invoice,
            "erp.attach_file": self.attach_file,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.BLOCKED,
                errors=[
                    ToolError(
                        code="erp.unsupported_tool",
                        message=f"Unsupported semantic ERP tool: {request.tool_name}",
                    )
                ],
            )

        try:
            return handler(request)
        except ERPNextClientError as exc:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.VALIDATION_ERROR,
                errors=[
                    ToolError(
                        code="erp.client_error",
                        message=str(exc),
                        status_code=exc.status_code,
                        details=exc.body,
                    )
                ],
                meta={"retryable": True},
            )
        except (KeyError, ValueError) as exc:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.VALIDATION_ERROR,
                errors=[
                    ToolError(code="erp.bad_request", message=str(exc))
                ],
                meta={"retryable": True},
            )

    def get_doc(self, request: ToolRequest) -> ToolResponse:
        command = GetDocCommand.model_validate(request.payload)
        doctype = command.doctype
        name = command.name
        fields = command.fields
        doc = self.client.get_doc(doctype, name)
        if fields:
            doc = {field: doc.get(field) for field in fields}
            doc.setdefault("doctype", doctype)
            doc.setdefault("name", name)
        return self._success(request, {"doc": doc})

    def list_docs(self, request: ToolRequest) -> ToolResponse:
        command = ListDocsCommand.model_validate(request.payload)
        docs = self.client.list_docs(
            command.doctype,
            filters=command.filters,
            fields=command.fields or None,
            order_by=command.order_by,
            limit=command.limit,
        )
        return self._success(request, {"docs": docs})

    def get_linked_context(self, request: ToolRequest) -> ToolResponse:
        command = LinkedContextCommand.model_validate(request.payload)
        subject = command.subject.as_dict()
        include = list(command.include)
        limit = command.limit_per_relation
        linked: dict[str, Any] = {}

        subject_name = str(subject["name"])
        subject_doctype = str(subject["doctype"])

        if "quotations" in include and subject_doctype == "Customer":
            linked["quotations"] = self.client.list_docs(
                "Quotation",
                filters={"party_name": subject_name},
                fields=["name", "transaction_date", "grand_total", "docstatus"],
                order_by="modified desc",
                limit=limit,
            )
        if "sales_invoices" in include and subject_doctype == "Customer":
            linked["sales_invoices"] = self.client.list_docs(
                "Sales Invoice",
                filters={"customer": subject_name},
                fields=["name", "posting_date", "grand_total", "docstatus"],
                order_by="modified desc",
                limit=limit,
            )
        if "projects" in include and subject_doctype == "Customer":
            linked["projects"] = self.client.list_docs(
                "Project",
                filters={"customer": subject_name},
                fields=["name", "project_name", "status"],
                order_by="modified desc",
                limit=limit,
            )
        if "purchase_invoices" in include and subject_doctype == "Supplier":
            linked["purchase_invoices"] = self.client.list_docs(
                "Purchase Invoice",
                filters={"supplier": subject_name},
                fields=["name", "posting_date", "grand_total", "docstatus"],
                order_by="modified desc",
                limit=limit,
            )
        if "pricing_context" in include:
            linked["pricing_context"] = self._pricing_context(
                items=command.items,
                customer=subject_name if subject_doctype == "Customer" else None,
                supplier=subject_name if subject_doctype == "Supplier" else None,
                limit=limit,
            )

        return self._success(
            request,
            {
                "subject": subject,
                "linked": linked,
            },
        )

    def get_pricing_context(self, request: ToolRequest) -> ToolResponse:
        command = PricingContextCommand.model_validate(request.payload)
        data = self._pricing_context(
            items=command.items,
            customer=command.customer,
            supplier=command.supplier,
            limit=10,
        )
        return self._success(request, data)

    def create_draft_quotation(self, request: ToolRequest) -> ToolResponse:
        command = CreateDraftQuotationCommand.model_validate(request.payload)
        doc = self._quotation_payload(command)
        if request.dry_run:
            return self._success(
                request,
                {
                    "doc_ref": {"doctype": "Quotation", "name": None},
                    "docstatus": 0,
                },
                meta={"dry_run": True, "proposed_doc": doc},
            )
        created = self.client.create_doc("Quotation", doc)
        return self._success(
            request,
            {
                "doc_ref": {"doctype": "Quotation", "name": created["name"]},
                "docstatus": created.get("docstatus", 0),
            },
        )

    def update_draft_quotation(self, request: ToolRequest) -> ToolResponse:
        command = UpdateDraftQuotationCommand.model_validate(request.payload)
        quotation = command.quotation
        patch = command.patch
        existing = self.client.get_doc("Quotation", quotation)
        if int(existing.get("docstatus", 0)) != 0:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=ToolExecutionStatus.BLOCKED,
                errors=[
                    ToolError(
                        code="erp.non_draft_document",
                        message=f"Quotation {quotation} is not in draft state",
                    )
                ],
                meta={"retryable": False},
            )

        updated = self._apply_quotation_patch(existing, patch)
        if request.dry_run:
            return self._success(
                request,
                {
                    "doc_ref": {"doctype": "Quotation", "name": quotation},
                    "docstatus": 0,
                },
                meta={"dry_run": True, "proposed_doc": updated},
            )
        saved = self.client.update_doc("Quotation", quotation, updated)
        return self._success(
            request,
            {
                "doc_ref": {"doctype": "Quotation", "name": saved["name"]},
                "docstatus": saved.get("docstatus", 0),
            },
        )

    def create_draft_purchase_invoice(self, request: ToolRequest) -> ToolResponse:
        command = CreateDraftPurchaseInvoiceCommand.model_validate(request.payload)
        supplier = command.supplier
        if not supplier:
            return self._approval_required(
                request,
                action="create_supplier",
                summary="Resolve or create a supplier before drafting the purchase invoice",
                target={"doctype": "Supplier", "name": None},
                proposed_changes={},
                warnings=["Supplier match is required for direct ERP write"],
            )

        doc = {
            "supplier": supplier,
            "bill_no": command.bill_no,
            "posting_date": command.posting_date,
            "items": command.items,
        }
        if request.dry_run:
            return self._success(
                request,
                {
                    "doc_ref": {"doctype": "Purchase Invoice", "name": None},
                    "docstatus": 0,
                },
                meta={"dry_run": True, "proposed_doc": doc},
            )

        created = self.client.create_doc("Purchase Invoice", doc)
        return self._success(
            request,
            {
                "doc_ref": {"doctype": "Purchase Invoice", "name": created["name"]},
                "docstatus": created.get("docstatus", 0),
            },
        )

    def attach_file(self, request: ToolRequest) -> ToolResponse:
        command = AttachFileCommand.model_validate(request.payload)
        target = command.target.as_dict()
        source_path = Path(command.source_path)
        if not source_path.is_absolute():
            source_path = self.config.paths.state_dir / source_path
        attachment = self.client.attach_file(
            target_doctype=command.target.doctype,
            target_name=str(command.target.name),
            source_path=source_path,
            file_name=str(command.file_name or "attachment.bin"),
            is_private=command.is_private,
        )
        return self._success(
            request,
            {
                "target": target,
                "attachment": attachment,
            },
        )

    def _success(
        self,
        request: ToolRequest,
        data: dict[str, Any],
        *,
        meta: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> ToolResponse:
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=ToolExecutionStatus.SUCCESS,
            data=data,
            warnings=warnings or [],
            meta=meta or {},
        )

    def _approval_required(
        self,
        request: ToolRequest,
        *,
        action: str,
        summary: str,
        target: dict[str, Any],
        proposed_changes: dict[str, Any],
        warnings: list[str],
    ) -> ToolResponse:
        approval_id = f"approval-{uuid.uuid4().hex}"
        approval = ApprovalPayload(
            approval_id=approval_id,
            action=action,
            summary=summary,
            target=target,
            proposed_changes=proposed_changes,
            artifacts=approval_artifact_paths(self.config.paths.approvals_dir, approval_id),
        )
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=ToolExecutionStatus.APPROVAL_REQUIRED,
            warnings=warnings,
            approval=approval,
        )

    def _quotation_payload(self, command: CreateDraftQuotationCommand) -> dict[str, Any]:
        doc = {
            "party_name": command.customer,
            "quotation_to": "Customer",
            "company": command.company,
            "currency": command.currency,
            "items": command.items,
        }
        narrative = command.narrative
        if "intro" in narrative:
            doc["remarks"] = narrative["intro"]
        if "notes" in narrative:
            doc["terms"] = narrative["notes"]
        return doc

    def _apply_quotation_patch(
        self, existing: dict[str, Any], patch: dict[str, Any]
    ) -> dict[str, Any]:
        updated = dict(existing)
        items = patch.get("items")
        if items is not None:
            replace_items = bool(patch.get("replace_items", False))
            current_items = [] if replace_items else list(existing.get("items", []))
            updated["items"] = current_items + list(items)

        notes_append = patch.get("notes_append", [])
        if notes_append:
            current_notes = str(existing.get("terms") or "")
            extra = "\n".join(str(note) for note in notes_append)
            updated["terms"] = extra if not current_notes else f"{current_notes}\n{extra}"
        return updated

    def _pricing_context(
        self,
        *,
        items: list[dict[str, Any]],
        customer: str | None,
        supplier: str | None,
        limit: int,
    ) -> dict[str, Any]:
        contexts: list[dict[str, Any]] = []
        for item in items:
            item_code = item.get("item_code")
            if not item_code:
                continue

            price_list_rates = self.client.list_docs(
                "Item Price",
                filters={"item_code": item_code},
                fields=["name", "price_list", "price_list_rate", "currency"],
                order_by="modified desc",
                limit=limit,
            )

            pricing_rules_filters: dict[str, Any] = {"item_code": item_code}
            if customer:
                pricing_rules_filters["customer"] = customer
            pricing_rules = self.client.list_docs(
                "Pricing Rule",
                filters=pricing_rules_filters,
                fields=["name", "title", "rate_or_discount", "discount_percentage"],
                order_by="modified desc",
                limit=limit,
            )

            recent_sales = self.client.list_docs(
                "Sales Invoice Item",
                filters={"item_code": item_code},
                fields=["parent", "item_code", "rate", "amount"],
                order_by="modified desc",
                limit=limit,
            )

            recent_purchases = self.client.list_docs(
                "Purchase Invoice Item",
                filters={"item_code": item_code},
                fields=["parent", "item_code", "rate", "amount"],
                order_by="modified desc",
                limit=limit,
            )

            contexts.append(
                {
                    "item_code": item_code,
                    "price_list_rates": price_list_rates,
                    "pricing_rules": pricing_rules,
                    "recent_sales": recent_sales,
                    "recent_purchases": recent_purchases,
                }
            )
        return {"items": contexts}
