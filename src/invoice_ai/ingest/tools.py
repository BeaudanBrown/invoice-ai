from __future__ import annotations

from typing import Any
import uuid

from ..config import RuntimeConfig
from ..erp.client import ERPNextClient
from ..erp.schemas import ApprovalPayload, ToolRequest, ToolResponse, approval_artifact_paths
from .models import SupplierInvoiceInput
from .normalize import SupplierInvoiceNormalizer
from .store import IngestStore


class IngestToolExecutor:
    def __init__(
        self,
        *,
        config: RuntimeConfig,
        erp_client: ERPNextClient | None = None,
    ) -> None:
        self.config = config
        self.erp_client = erp_client
        self.normalizer = SupplierInvoiceNormalizer(erp_client)
        self.store = IngestStore(config.paths.ingest_dir)

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "IngestToolExecutor":
        erp_client = None
        if config.dependencies.erpnext_url is not None:
            erp_client = ERPNextClient.from_runtime_config(config)
        return cls(config=config, erp_client=erp_client)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "ingest.normalize_supplier_invoice": self.normalize_supplier_invoice,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "ingest.unsupported_tool",
                        "message": f"Unsupported ingest tool: {request.tool_name}",
                    }
                ],
            )
        return handler(request)

    def normalize_supplier_invoice(self, request: ToolRequest) -> ToolResponse:
        source = SupplierInvoiceInput.from_payload(request.request_id, request.payload)
        normalized = self.normalizer.normalize(source)
        if normalized["resolved"]:
            record_dir = self.store.write_processed(
                request_id=request.request_id,
                source=source.as_dict(),
                normalized=normalized,
            )
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="success",
                data={
                    "normalized_invoice": normalized,
                    "purchase_invoice_request": {
                        "request_id": request.request_id,
                        "tool_name": "erp.create_draft_purchase_invoice",
                        "dry_run": request.dry_run,
                        "conversation_context": request.conversation_context,
                        "payload": normalized["purchase_invoice_payload"],
                    },
                },
                meta={"ingest_record_dir": str(record_dir)},
            )

        record_dir = self.store.write_processed(
            request_id=request.request_id,
            source=source.as_dict(),
            normalized=normalized,
        )
        missing = normalized["missing_master_data"]
        approval_id = f"approval-{uuid.uuid4().hex}"
        approval = ApprovalPayload(
            approval_id=approval_id,
            action="review_purchase_invoice_proposal",
            summary="Resolve missing supplier or item mappings before creating a draft purchase invoice",
            target={"doctype": "Purchase Invoice", "name": None},
            proposed_changes=missing,
            artifacts=approval_artifact_paths(self.config.paths.approvals_dir, approval_id),
        )
        warnings = []
        if missing.get("supplier") is not None:
            warnings.append("Supplier resolution is missing or low confidence")
        if missing.get("items"):
            warnings.append("One or more line items could not be matched to existing ERP items")
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="approval_required",
            data={
                "normalized_invoice": normalized,
                "proposed_purchase_invoice_request": {
                    "request_id": request.request_id,
                    "tool_name": "erp.create_draft_purchase_invoice",
                    "dry_run": True,
                    "conversation_context": request.conversation_context,
                    "payload": normalized["purchase_invoice_payload"],
                },
            },
            warnings=warnings,
            approval=approval,
            meta={"ingest_record_dir": str(record_dir)},
        )
