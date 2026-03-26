from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import uuid

from ..config import RuntimeConfig
from ..erp.schemas import ApprovalPayload, ToolRequest, ToolResponse, approval_artifact_paths
from ..erp.tools import ERPToolExecutor
from .models import InvoiceDraftRequest, InvoiceLineIntent


@dataclass
class InvoiceContextBuilder:
    config: RuntimeConfig
    erp: ERPToolExecutor

    def build(
        self, request: InvoiceDraftRequest
    ) -> tuple[dict[str, Any] | None, ToolResponse | None]:
        if request.quotation is not None:
            return self._build_from_quotation(request)

        customer = self._resolve_customer(request)
        unresolved = []
        if customer is None:
            unresolved.append(
                {
                    "kind": "customer",
                    "lookup": request.customer or request.customer_name,
                }
            )

        resolved_lines = []
        pricing_items = []
        for line in request.line_items:
            resolved = self._resolve_item(line)
            if resolved is None:
                unresolved.append({"kind": "item", "lookup": line.lookup_label()})
                continue
            pricing_items.append({"item_code": resolved["item_code"]})
            resolved_lines.append(resolved)

        if unresolved:
            return None, self._approval_for_unresolved(request, unresolved)

        linked_context = self._linked_customer_context(
            request=request,
            customer_name=str(customer["name"]),
            pricing_items=pricing_items,
        )
        pricing_context = linked_context.get("pricing_context", {"items": []})

        enriched_lines = []
        for resolved in resolved_lines:
            resolved["rate"] = self._choose_rate(
                item_code=str(resolved["item_code"]),
                explicit_rate=resolved.get("rate"),
                pricing_context=pricing_context,
            )
            enriched_lines.append(resolved)

        return {
            "draft_key": request.draft_key,
            "customer": customer,
            "line_items": enriched_lines,
            "linked": linked_context,
            "pricing_context": pricing_context,
            "source_quotation": None,
        }, None

    def _build_from_quotation(
        self, request: InvoiceDraftRequest
    ) -> tuple[dict[str, Any] | None, ToolResponse | None]:
        response = self.erp.execute(
            ToolRequest(
                request_id=f"{request.request_id}-quotation-context",
                tool_name="erp.get_doc",
                dry_run=False,
                payload={"doctype": "Quotation", "name": request.quotation},
                conversation_context={"draft_key": request.draft_key},
            )
        )
        if response.status != "success":
            return None, response

        quotation_doc = dict(response.data.get("doc", {}))
        if int(quotation_doc.get("docstatus", 0)) not in {0, 1}:
            return None, ToolResponse(
                request_id=request.request_id,
                tool_name="invoices.create_draft",
                status="blocked",
                errors=[
                    {
                        "code": "invoices.invalid_quotation_state",
                        "message": f"Quotation {request.quotation} is not usable for invoice drafting",
                    }
                ],
            )

        customer_name = str(
            quotation_doc.get("party_name")
            or quotation_doc.get("customer")
            or quotation_doc.get("customer_name")
            or ""
        )
        customer = {
            "name": customer_name,
            "customer_name": str(quotation_doc.get("customer_name") or customer_name),
        }
        line_items = [
            {
                "item_code": item.get("item_code"),
                "item_name": item.get("item_name"),
                "description": item.get("description") or item.get("item_name") or item.get("item_code"),
                "qty": float(item.get("qty") or 0),
                "rate": float(item.get("rate") or 0),
                "quotation": request.quotation,
                "quotation_item": item.get("name"),
            }
            for item in quotation_doc.get("items", [])
        ]
        linked_context = self._linked_customer_context(
            request=request,
            customer_name=customer_name,
            pricing_items=[
                {"item_code": item["item_code"]}
                for item in line_items
                if item.get("item_code")
            ],
        )

        return {
            "draft_key": request.draft_key,
            "customer": customer,
            "line_items": line_items,
            "linked": linked_context,
            "pricing_context": linked_context.get("pricing_context", {"items": []}),
            "source_quotation": request.quotation,
            "quotation_doc": quotation_doc,
        }, None

    def _resolve_customer(self, request: InvoiceDraftRequest) -> dict[str, Any] | None:
        selectors = []
        if request.customer:
            selectors.append({"name": request.customer})
            selectors.append({"customer_name": request.customer})
        if request.customer_name and request.customer_name != request.customer:
            selectors.append({"customer_name": request.customer_name})
            selectors.append({"name": request.customer_name})

        for filters in selectors:
            response = self.erp.execute(
                ToolRequest(
                    request_id=f"{request.request_id}-customer-{uuid.uuid4().hex[:8]}",
                    tool_name="erp.list_docs",
                    dry_run=False,
                    payload={
                        "doctype": "Customer",
                        "filters": filters,
                        "fields": ["name", "customer_name", "customer_group", "territory"],
                        "limit": 2,
                    },
                )
            )
            docs = response.data.get("docs", [])
            if response.status == "success" and docs:
                return dict(docs[0])
        return None

    def _resolve_item(self, line: InvoiceLineIntent) -> dict[str, Any] | None:
        selectors = []
        if line.item_code:
            selectors.append({"item_code": line.item_code})
            selectors.append({"name": line.item_code})
        if line.item_name:
            selectors.append({"item_name": line.item_name})
            selectors.append({"name": line.item_name})

        for filters in selectors:
            response = self.erp.execute(
                ToolRequest(
                    request_id=f"{filters.get('name', filters.get('item_code', 'item'))}-{uuid.uuid4().hex[:8]}",
                    tool_name="erp.list_docs",
                    dry_run=False,
                    payload={
                        "doctype": "Item",
                        "filters": filters,
                        "fields": ["name", "item_code", "item_name", "stock_uom"],
                        "limit": 2,
                    },
                )
            )
            docs = response.data.get("docs", [])
            if response.status == "success" and docs:
                doc = dict(docs[0])
                return {
                    "item_code": doc.get("item_code") or doc.get("name"),
                    "item_name": doc.get("item_name"),
                    "description": line.description or doc.get("item_name") or doc.get("item_code"),
                    "qty": line.qty,
                    "rate": line.rate,
                }
        return None

    def _linked_customer_context(
        self,
        *,
        request: InvoiceDraftRequest,
        customer_name: str,
        pricing_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        response = self.erp.execute(
            ToolRequest(
                request_id=f"{request.request_id}-context",
                tool_name="erp.get_linked_context",
                dry_run=False,
                payload={
                    "subject": {"doctype": "Customer", "name": customer_name},
                    "include": ["quotations", "sales_invoices", "projects", "pricing_context"],
                    "items": pricing_items,
                    "limit": 10,
                },
                conversation_context={"draft_key": request.draft_key},
            )
        )
        if response.status != "success":
            return {}
        return dict(response.data.get("linked", {}))

    def _choose_rate(
        self,
        *,
        item_code: str,
        explicit_rate: Any,
        pricing_context: dict[str, Any],
    ) -> float:
        if explicit_rate is not None:
            return float(explicit_rate)

        for item_context in pricing_context.get("items", []):
            if item_context.get("item_code") != item_code:
                continue
            price_list_rates = item_context.get("price_list_rates", [])
            if price_list_rates:
                return float(price_list_rates[0].get("price_list_rate", 0))
            recent_sales = item_context.get("recent_sales", [])
            if recent_sales:
                return float(recent_sales[0].get("rate", 0))
        return 0.0

    def _approval_for_unresolved(
        self,
        request: InvoiceDraftRequest,
        unresolved: list[dict[str, Any]],
    ) -> ToolResponse:
        approval_id = f"approval-{uuid.uuid4().hex}"
        return ToolResponse(
            request_id=request.request_id,
            tool_name="invoices.create_draft",
            status="approval_required",
            warnings=[
                "Sales invoice drafting requires existing ERP customer and item masters"
            ],
            approval=ApprovalPayload(
                approval_id=approval_id,
                action="review_sales_invoice_master_data",
                summary=(
                    "Resolve missing customer or item mappings before creating a "
                    "draft sales invoice"
                ),
                target={"doctype": "Sales Invoice", "name": None},
                proposed_changes={"unresolved": unresolved},
                artifacts=approval_artifact_paths(
                    self.config.paths.approvals_dir, approval_id
                ),
            ),
            data={
                "draft_key": request.draft_key,
                "requested_customer": request.customer or request.customer_name,
                "requested_items": [line.as_dict() for line in request.line_items],
                "source_quotation": request.quotation,
            },
        )
