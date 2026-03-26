from __future__ import annotations

from pathlib import Path
from typing import Any
import uuid

from pydantic import ValidationError

from ..config import RuntimeConfig
from ..control_plane.store import ControlPlaneStore
from ..erp.client import ERPNextClient
from ..erp.schemas import ApprovalPayload, ToolRequest, ToolResponse, approval_artifact_paths
from ..erp.tools import ERPToolExecutor
from ..extract.tools import ExtractToolExecutor
from .models import SupplierInvoiceInput
from .normalize import SupplierInvoiceNormalizer
from .store import IngestStore


class IngestToolExecutor:
    def __init__(
        self,
        *,
        config: RuntimeConfig,
        erp_client: ERPNextClient | None = None,
        erp_executor: ERPToolExecutor | None = None,
        extract_executor: ExtractToolExecutor | None = None,
    ) -> None:
        self.config = config
        self.control_plane = ControlPlaneStore.from_runtime_config(config)
        self.erp_client = erp_client
        self.erp_executor = erp_executor
        self.extract_executor = extract_executor
        self.normalizer = SupplierInvoiceNormalizer(erp_client)
        self.store = IngestStore(
            config.paths.ingest_dir,
            control_plane=self.control_plane,
        )

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "IngestToolExecutor":
        erp_client = None
        erp_executor = None
        if config.dependencies.erpnext_url is not None:
            erp_client = ERPNextClient.from_runtime_config(config)
            erp_executor = ERPToolExecutor(config=config, client=erp_client)
        return cls(
            config=config,
            erp_client=erp_client,
            erp_executor=erp_executor,
            extract_executor=ExtractToolExecutor.from_runtime_config(config),
        )

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "ingest.normalize_supplier_invoice": self.normalize_supplier_invoice,
            "ingest.create_purchase_invoice_draft": self.create_purchase_invoice_draft,
            "ingest.process_supplier_document": self.process_supplier_document,
            "ingest.reprocess_record": self.reprocess_record,
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
        try:
            return handler(request)
        except (ValidationError, ValueError) as exc:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[{"code": "ingest.bad_request", "message": str(exc)}],
            )

    def normalize_supplier_invoice(self, request: ToolRequest) -> ToolResponse:
        source = SupplierInvoiceInput.from_payload(request.request_id, request.payload)
        normalized, record_dir = self._normalize_and_store(
            source=source, request_id=request.request_id
        )
        duplicate_response = self._duplicate_response(
            request=request,
            source=source,
            normalized=normalized,
            record_dir=record_dir,
        )
        if duplicate_response is not None:
            self._persist_composed_result(record_dir=record_dir, response=duplicate_response)
            return duplicate_response
        if normalized["resolved"]:
            response = ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="success",
                data={
                    "normalized_invoice": normalized,
                    "purchase_invoice_request": self._purchase_invoice_request_dict(
                        request=request,
                        payload=normalized["purchase_invoice_payload"],
                    ),
                },
                meta={"ingest_record_dir": str(record_dir)},
            )
            self._persist_composed_result(record_dir=record_dir, response=response)
            return response

        response = self._approval_response(
            request=request,
            normalized=normalized,
            record_dir=record_dir,
        )
        self._persist_composed_result(record_dir=record_dir, response=response)
        return response

    def process_supplier_document(self, request: ToolRequest) -> ToolResponse:
        if self.extract_executor is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "ingest.extract_unavailable",
                        "message": "Document extraction is not available for supplier document processing",
                    }
                ],
            )

        extract_request = ToolRequest(
            request_id=request.request_id,
            tool_name="extract.supplier_invoice_from_document",
            dry_run=request.dry_run,
            payload=dict(request.payload),
            conversation_context=request.conversation_context,
        )
        extract_response = self.extract_executor.execute(extract_request)
        if extract_response.status != "success":
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=extract_response.status,
                data={
                    "stage": "extract",
                    "extract_response": extract_response.as_dict(),
                },
                errors=extract_response.errors,
                warnings=extract_response.warnings,
                approval=extract_response.approval,
                meta=extract_response.meta,
            )

        next_request = dict(extract_response.data["next_request"])
        next_payload = dict(next_request.get("payload", {}))
        next_payload["attach_source_file"] = bool(
            request.payload.get("attach_source_file", True)
        )
        if "file_name" in request.payload:
            next_payload["file_name"] = request.payload["file_name"]
        if "is_private" in request.payload:
            next_payload["is_private"] = request.payload["is_private"]

        create_request = ToolRequest.from_dict(
            {
                **next_request,
                "request_id": request.request_id,
                "tool_name": "ingest.create_purchase_invoice_draft",
                "dry_run": request.dry_run,
                "conversation_context": request.conversation_context,
                "payload": next_payload,
            }
        )
        create_response = self.create_purchase_invoice_draft(create_request)
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=create_response.status,
            data={
                "stage": "ingest",
                "extract_response": extract_response.as_dict(),
                "pipeline_response": create_response.as_dict(),
            },
            errors=create_response.errors,
            warnings=[*extract_response.warnings, *create_response.warnings],
            approval=create_response.approval,
            meta={
                **extract_response.meta,
                **create_response.meta,
                "pipeline_stages": ["extract", "ingest"],
            },
        )

    def create_purchase_invoice_draft(self, request: ToolRequest) -> ToolResponse:
        source = SupplierInvoiceInput.from_payload(request.request_id, request.payload)
        normalized, record_dir = self._normalize_and_store(
            source=source, request_id=request.request_id
        )
        duplicate_response = self._duplicate_response(
            request=request,
            source=source,
            normalized=normalized,
            record_dir=record_dir,
        )
        if duplicate_response is not None:
            self._persist_composed_result(record_dir=record_dir, response=duplicate_response)
            return duplicate_response
        if not normalized["resolved"]:
            response = self._approval_response(
                request=request,
                normalized=normalized,
                record_dir=record_dir,
            )
            self._persist_composed_result(record_dir=record_dir, response=response)
            return response

        if self.erp_executor is None:
            response = ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "ingest.erp_unavailable",
                        "message": "ERPNext is not configured for draft purchase invoice creation",
                    }
                ],
                meta={"ingest_record_dir": str(record_dir)},
            )
            self._persist_composed_result(record_dir=record_dir, response=response)
            return response

        purchase_invoice_request = ToolRequest.from_dict(
            self._purchase_invoice_request_dict(
                request=request,
                payload=normalized["purchase_invoice_payload"],
            )
        )
        create_response = self.erp_executor.execute(purchase_invoice_request)
        if create_response.status != "success":
            response = ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=create_response.status,
                data={
                    "normalized_invoice": normalized,
                    "purchase_invoice_request": purchase_invoice_request.payload,
                    "erp_create_response": create_response.as_dict(),
                },
                errors=create_response.errors,
                warnings=create_response.warnings,
                approval=create_response.approval,
                meta={
                    "ingest_record_dir": str(record_dir),
                    **create_response.meta,
                },
            )
            self._persist_composed_result(record_dir=record_dir, response=response)
            return response

        attachment_result: dict[str, Any] | None = None
        warnings = list(create_response.warnings)
        if (
            bool(request.payload.get("attach_source_file", True))
            and source.source_path
            and create_response.data.get("doc_ref", {}).get("name")
        ):
            attachment_request = ToolRequest(
                request_id=f"{request.request_id}-attach",
                tool_name="erp.attach_file",
                dry_run=request.dry_run,
                payload={
                    "target": create_response.data["doc_ref"],
                    "source_path": source.source_path,
                    "file_name": request.payload.get("file_name") or source.source_path.rsplit("/", 1)[-1],
                    "is_private": bool(request.payload.get("is_private", True)),
                },
                conversation_context=request.conversation_context,
            )
            attachment_response = self.erp_executor.execute(attachment_request)
            attachment_result = attachment_response.as_dict()
            if attachment_response.status != "success":
                warnings.append("Draft purchase invoice created but source attachment failed")

        response = ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "normalized_invoice": normalized,
                "purchase_invoice": create_response.data,
                "purchase_invoice_request": purchase_invoice_request.payload,
                "attachment": attachment_result,
            },
            warnings=warnings,
            meta={
                "ingest_record_dir": str(record_dir),
                **create_response.meta,
            },
        )
        self._persist_composed_result(record_dir=record_dir, response=response)
        return response

    def reprocess_record(self, request: ToolRequest) -> ToolResponse:
        record_dir_value = request.payload.get("record_dir")
        if not record_dir_value:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[
                    {
                        "code": "ingest.missing_record_dir",
                        "message": "ingest.reprocess_record requires record_dir",
                    }
                ],
            )

        record = self.store.load_record(record_dir=Path(str(record_dir_value)))
        source_record = dict(record.get("source", {})).get("source", {})
        extracted_record = dict(record.get("extracted", {})).get("extracted", {})
        overrides = dict(request.payload.get("overrides", {}))

        if extracted_record.get("candidate"):
            payload = {
                "source_ref": {
                    "source_type": source_record.get("source_type"),
                    "source_path": source_record.get("source_path"),
                    "source_hash": source_record.get("source_hash"),
                },
                "extracted_invoice": dict(extracted_record["candidate"]),
                **overrides,
            }
            replay_request = ToolRequest(
                request_id=request.request_id,
                tool_name="ingest.create_purchase_invoice_draft",
                dry_run=request.dry_run,
                payload=payload,
                conversation_context=request.conversation_context,
            )
            response = self.create_purchase_invoice_draft(replay_request)
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=response.status,
                data={
                    "reprocessed_from": str(record["record_dir"]),
                    "replay_mode": "extracted_invoice",
                    "pipeline_response": response.as_dict(),
                },
                errors=response.errors,
                warnings=response.warnings,
                approval=response.approval,
                meta=response.meta,
            )

        source_payload = {**source_record, **overrides}
        if source_payload.get("supplier_name") and source_payload.get("lines"):
            replay_request = ToolRequest(
                request_id=request.request_id,
                tool_name="ingest.create_purchase_invoice_draft",
                dry_run=request.dry_run,
                payload=source_payload,
                conversation_context=request.conversation_context,
            )
            response = self.create_purchase_invoice_draft(replay_request)
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status=response.status,
                data={
                    "reprocessed_from": str(record["record_dir"]),
                    "replay_mode": "supplier_invoice_input",
                    "pipeline_response": response.as_dict(),
                },
                errors=response.errors,
                warnings=response.warnings,
                approval=response.approval,
                meta=response.meta,
            )

        replay_request = ToolRequest(
            request_id=request.request_id,
            tool_name="ingest.process_supplier_document",
            dry_run=request.dry_run,
            payload=source_payload,
            conversation_context=request.conversation_context,
        )
        response = self.process_supplier_document(replay_request)
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=response.status,
            data={
                "reprocessed_from": str(record["record_dir"]),
                "replay_mode": "document_source",
                "pipeline_response": response.as_dict(),
            },
            errors=response.errors,
            warnings=response.warnings,
            approval=response.approval,
            meta=response.meta,
        )

    def _normalize_and_store(
        self,
        *,
        source: SupplierInvoiceInput,
        request_id: str,
    ) -> tuple[dict[str, Any], Path]:
        normalized = self.normalizer.normalize(source)
        record_dir = self.store.write_processed(
            request_id=request_id,
            source=source.as_dict(),
            normalized=normalized,
        )
        return normalized, record_dir

    def _approval_response(
        self,
        *,
        request: ToolRequest,
        normalized: dict[str, Any],
        record_dir: Path,
    ) -> ToolResponse:
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
                "proposed_purchase_invoice_request": self._purchase_invoice_request_dict(
                    request=request,
                    payload=normalized["purchase_invoice_payload"],
                    dry_run=True,
                ),
            },
            warnings=warnings,
            approval=approval,
            meta={"ingest_record_dir": str(record_dir)},
        )

    def _purchase_invoice_request_dict(
        self,
        *,
        request: ToolRequest,
        payload: dict[str, Any] | None,
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        sanitized_payload = dict(payload or {})
        sanitized_payload.pop("source_ref", None)
        return {
            "request_id": request.request_id,
            "tool_name": "erp.create_draft_purchase_invoice",
            "dry_run": request.dry_run if dry_run is None else dry_run,
            "conversation_context": request.conversation_context,
            "payload": sanitized_payload,
        }

    def _duplicate_response(
        self,
        *,
        request: ToolRequest,
        source: SupplierInvoiceInput,
        normalized: dict[str, Any],
        record_dir: Path,
    ) -> ToolResponse | None:
        supplier_hint = (
            dict(normalized.get("supplier", {})).get("supplier_name") or source.supplier_name
        )
        external_invoice_reference = (
            dict(normalized.get("invoice", {})).get("supplier_invoice_ref")
            or source.supplier_invoice_ref
        )
        duplicates = self.control_plane.find_duplicate_ingests(
            source_fingerprint=source.source_hash,
            supplier_hint=supplier_hint,
            external_invoice_reference=external_invoice_reference,
            exclude_request_id=request.request_id,
        )
        if not duplicates:
            return None

        approval_id = f"approval-{uuid.uuid4().hex}"
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="approval_required",
            data={
                "normalized_invoice": normalized,
                "duplicate_candidates": duplicates,
                "proposed_purchase_invoice_request": self._purchase_invoice_request_dict(
                    request=request,
                    payload=normalized.get("purchase_invoice_payload"),
                    dry_run=True,
                ),
            },
            warnings=["Possible duplicate supplier invoice detected"],
            approval=ApprovalPayload(
                approval_id=approval_id,
                action="review_duplicate_supplier_invoice",
                summary=(
                    "Review possible duplicate supplier invoice before creating a draft purchase invoice"
                ),
                target={"doctype": "Purchase Invoice", "name": None},
                proposed_changes={
                    "duplicates": duplicates,
                    "source_hash": source.source_hash,
                    "supplier_invoice_ref": external_invoice_reference,
                },
                artifacts=approval_artifact_paths(self.config.paths.approvals_dir, approval_id),
            ),
            meta={"ingest_record_dir": str(record_dir)},
        )

    def _persist_composed_result(
        self,
        *,
        record_dir: Path,
        response: ToolResponse,
    ) -> None:
        self.store.write_composed_result(
            record_dir=record_dir,
            result=response.as_dict(),
        )
