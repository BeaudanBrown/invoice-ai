from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..config import RuntimeConfig
from ..erp.schemas import ToolRequest, ToolResponse
from ..ingest.tools import IngestToolExecutor
from ..invoices.tools import InvoiceToolExecutor
from ..memory.tools import MemoryToolExecutor
from ..quotes.tools import QuoteToolExecutor
from .contract import conversation_state_for, next_request_contract
from .models import OperatorRequest


class OrchestratorToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.ingest = IngestToolExecutor.from_runtime_config(config)
        self.invoices = InvoiceToolExecutor.from_runtime_config(config)
        self.memory = MemoryToolExecutor.from_runtime_config(config)
        self.quotes = QuoteToolExecutor.from_runtime_config(config)

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "OrchestratorToolExecutor":
        return cls(config=config)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "orchestrator.handle_request": self.handle_request,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "orchestrator.unsupported_tool",
                        "message": f"Unsupported orchestrator tool: {request.tool_name}",
                    }
                ],
            )
        return handler(request)

    def handle_request(self, request: ToolRequest) -> ToolResponse:
        try:
            operator_request = OperatorRequest.from_payload(
                request.request_id,
                request.payload,
                conversation_context=request.conversation_context,
            )
        except (ValidationError, ValueError) as exc:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[
                    {
                        "code": "orchestrator.bad_request",
                        "message": str(exc),
                    }
                ],
            )

        delegated_tool = operator_request.delegated_tool_name()
        delegated_request = ToolRequest(
            request_id=request.request_id,
            tool_name=delegated_tool,
            dry_run=request.dry_run,
            payload=operator_request.delegated_payload(),
            conversation_context=request.conversation_context,
        )
        delegated_response = self._executor_for(delegated_tool).execute(delegated_request)
        stage = _stage_for(operator_request.request_kind, delegated_response)
        artifacts = _collect_artifacts(delegated_response)
        erp_refs = _collect_erp_refs(
            request_kind=operator_request.request_kind,
            response=delegated_response,
        )
        conversation_state = conversation_state_for(
            request_kind=operator_request.request_kind,
            response=delegated_response,
        )

        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=delegated_response.status,
            data={
                "request_kind": operator_request.request_kind,
                "operator_message": operator_request.operator_message,
                "stage": stage,
                "delegate": {
                    "tool_name": delegated_tool,
                    "status": delegated_response.status,
                },
                "artifacts": artifacts,
                "erp_refs": erp_refs,
                "conversation_state": conversation_state,
                "next_request_contract": next_request_contract(
                    request_kind=operator_request.request_kind,
                    response=delegated_response,
                ),
                "delegated_response": delegated_response.as_dict(),
            },
            errors=delegated_response.errors,
            warnings=delegated_response.warnings,
            approval=delegated_response.approval,
            meta={
                **delegated_response.meta,
                "request_kind": operator_request.request_kind,
                "delegated_tool": delegated_tool,
                "stage": stage,
            },
        )

    def _executor_for(self, tool_name: str) -> object:
        if tool_name.startswith("ingest."):
            return self.ingest
        if tool_name.startswith("invoices."):
            return self.invoices
        if tool_name.startswith("memory."):
            return self.memory
        if tool_name.startswith("quotes."):
            return self.quotes
        raise ValueError(f"Unsupported orchestrator delegate: {tool_name}")


def _stage_for(request_kind: str, response: ToolResponse) -> str:
    if request_kind == "review_queue":
        if response.status == "success":
            return "review_queue_listed"
        return "review_queue"

    if request_kind == "supplier_document_intake":
        delegated_stage = str(response.data.get("stage") or "")
        if response.status == "success":
            return "purchase_invoice_draft_created"
        if delegated_stage == "extract":
            return "extract_review"
        if delegated_stage == "ingest":
            return "ingest_review"
        return delegated_stage or "supplier_document_intake"

    if request_kind == "quote_revision":
        if response.status == "success":
            return "quotation_draft_revised"
        return "quote_revision"

    if request_kind == "invoice_revision":
        if response.status == "success":
            return "sales_invoice_draft_revised"
        return "invoice_revision"

    if request_kind == "invoice_draft":
        if response.status == "success":
            if response.data.get("source_quotation"):
                return "sales_invoice_draft_created_from_quotation"
            return "sales_invoice_draft_created"
        if response.status == "approval_required":
            return "sales_invoice_context_review"
        return "invoice_draft"

    if response.status == "success":
        return "quotation_draft_created"
    if response.status == "approval_required":
        return "quote_context_review"
    return "quote_draft"


def _collect_artifacts(response: ToolResponse) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    approval = response.approval
    if approval is not None:
        for artifact_kind, path in approval.artifacts.as_dict().items():
            if path is None:
                continue
            artifacts.append({"kind": artifact_kind, "path": path})

    preview_path = _find_preview_path(response.as_dict())
    if preview_path is not None:
        artifacts.append(
            {
                "kind": (
                    "sales_invoice_preview_pdf"
                    if response.data.get("sales_invoice") is not None
                    else "quote_preview_pdf"
                ),
                "path": preview_path,
            }
        )

    ingest_record_dir = response.meta.get("ingest_record_dir")
    if ingest_record_dir:
        artifacts.append({"kind": "ingest_record_dir", "path": str(ingest_record_dir)})

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for artifact in artifacts:
        key = (str(artifact["kind"]), str(artifact["path"]))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(artifact)
    return deduped


def _find_preview_path(payload: dict[str, Any]) -> str | None:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return None

    preview = data.get("preview")
    if isinstance(preview, dict) and preview.get("path"):
        return str(preview["path"])

    revision = data.get("revision")
    if isinstance(revision, dict) and revision.get("preview_path"):
        return str(revision["preview_path"])

    delegated = data.get("delegated_response")
    if isinstance(delegated, dict):
        return _find_preview_path(delegated)
    return None


def _collect_doc_refs(payload: Any) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            doc_ref = node.get("doc_ref")
            if isinstance(doc_ref, dict):
                doctype = doc_ref.get("doctype")
                name = doc_ref.get("name")
                if doctype is not None:
                    refs.append({"doctype": str(doctype), "name": None if name is None else str(name)})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for ref in refs:
        key = (ref["doctype"], ref["name"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped


def _collect_erp_refs(*, request_kind: str, response: ToolResponse) -> list[dict[str, Any]]:
    if request_kind == "review_queue":
        return []
    refs = _collect_doc_refs(response.as_dict())
    data = response.data

    if request_kind in {"quote_draft", "quote_revision"} and "quotation" in data:
        refs.append(
            {
                "doctype": "Quotation",
                "name": None if data.get("quotation") is None else str(data["quotation"]),
            }
        )
    if request_kind in {"invoice_draft", "invoice_revision"} and "sales_invoice" in data:
        refs.append(
            {
                "doctype": "Sales Invoice",
                "name": None
                if data.get("sales_invoice") is None
                else str(data["sales_invoice"]),
            }
        )
    if request_kind == "invoice_draft" and data.get("source_quotation") is not None:
        refs.append(
            {
                "doctype": "Quotation",
                "name": str(data["source_quotation"]),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for ref in refs:
        key = (ref["doctype"], ref["name"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return deduped
