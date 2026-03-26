from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from pydantic import ValidationError

from ..config import RuntimeConfig
from ..control_plane.store import ControlPlaneStore
from ..erp.schemas import ApprovalPayload, ToolRequest, ToolResponse, approval_artifact_paths
from ..ingest.store import IngestStore
from .docling import DoclingClient, DoclingClientError
from .models import DocumentSource
from .parser import parse_supplier_invoice_text


class ExtractToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.store = IngestStore(
            config.paths.ingest_dir,
            control_plane=ControlPlaneStore.from_runtime_config(config),
        )
        self.docling = (
            DoclingClient(config.dependencies.docling_url)
            if config.dependencies.docling_url is not None
            else None
        )

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "ExtractToolExecutor":
        return cls(config=config)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "extract.supplier_invoice_from_document": self.extract_supplier_invoice_from_document,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "extract.unsupported_tool",
                        "message": f"Unsupported extract tool: {request.tool_name}",
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
                errors=[{"code": "extract.bad_request", "message": str(exc)}],
            )

    def extract_supplier_invoice_from_document(self, request: ToolRequest) -> ToolResponse:
        source = self._enriched_source(DocumentSource.from_payload(request.payload))
        try:
            text, method = self._extract_text(source)
        except (OSError, DoclingClientError, ValueError) as exc:
            record_dir = self.store.write_rejected(
                request_id=request.request_id,
                source=source.as_dict(),
                error_summary={"message": str(exc)},
            )
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[{"code": "extract.read_failed", "message": str(exc)}],
                meta={"ingest_record_dir": str(record_dir)},
            )

        candidate = parse_supplier_invoice_text(text)
        record_dir = self.store.write_extracted(
            request_id=request.request_id,
            source=source.as_dict(),
            extracted={
                "document_text": text,
                "extraction_method": method,
                "candidate": candidate.as_dict(),
            },
        )
        next_request = {
            "request_id": request.request_id,
            "tool_name": "ingest.normalize_supplier_invoice",
            "dry_run": request.dry_run,
            "conversation_context": request.conversation_context,
            "payload": {
                "source_ref": {
                    "source_type": source.source_type,
                    "source_path": source.source_path,
                    "source_hash": source.source_hash,
                },
                "extracted_invoice": candidate.as_extracted_invoice(),
            },
        }

        if candidate.confidence < 0.7:
            approval_id = f"approval-{request.request_id}"
            approval = ApprovalPayload(
                approval_id=approval_id,
                action="review_extracted_supplier_invoice",
                summary="Review low-confidence supplier invoice extraction before ERP normalization",
                target={"doctype": "Purchase Invoice", "name": None},
                proposed_changes=candidate.as_extracted_invoice(),
                artifacts=approval_artifact_paths(self.config.paths.approvals_dir, approval_id),
            )
            response = ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="approval_required",
                data={
                    "source": source.as_dict(),
                    "extracted_invoice": candidate.as_dict(),
                    "anomalies": list(candidate.anomalies),
                    "next_request": next_request,
                },
                warnings=[*candidate.warnings, *candidate.anomalies],
                approval=approval,
                meta={"ingest_record_dir": str(record_dir), "extraction_method": method},
            )
            self.store.write_composed_result(record_dir=record_dir, result=response.as_dict())
            return response

        response = ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "source": source.as_dict(),
                "extracted_invoice": candidate.as_dict(),
                "anomalies": list(candidate.anomalies),
                "next_request": next_request,
            },
            warnings=[*candidate.warnings, *candidate.anomalies],
            meta={"ingest_record_dir": str(record_dir), "extraction_method": method},
        )
        self.store.write_composed_result(record_dir=record_dir, result=response.as_dict())
        return response

    def _enriched_source(self, source: DocumentSource) -> DocumentSource:
        if source.source_hash is not None:
            return source
        return replace(
            source,
            source_hash=source.computed_hash(state_dir=self.config.paths.state_dir),
        )

    def _extract_text(self, source: DocumentSource) -> tuple[str, str]:
        if source.raw_text is not None:
            return source.raw_text, "raw_text"

        resolved_path = source.resolved_path(state_dir=self.config.paths.state_dir)
        if resolved_path is None:
            raise ValueError("Document extraction requires raw_text or source_path")

        suffix = resolved_path.suffix.lower()
        if suffix == ".pdf":
            if self.docling is None:
                raise ValueError("PDF extraction requires INVOICE_AI_DOCLING_URL")
            payload = self.docling.extract_text(resolved_path)
            text = str(
                payload.get("document_text")
                or payload.get("text")
                or payload.get("markdown")
                or ""
            ).strip()
            if not text:
                raise ValueError("Docling did not return document text")
            return text, "docling_pdf"

        return resolved_path.read_text(encoding="utf-8"), "local_text"
