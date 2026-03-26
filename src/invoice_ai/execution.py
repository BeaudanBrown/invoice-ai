from __future__ import annotations

from hashlib import sha256

from .approvals.store import ApprovalStore
from .config import RuntimeConfig
from .control_plane.models import JobStatus, RequestSource
from .control_plane.store import ControlPlaneStore
from .erp.schemas import ToolExecutionStatus, ToolRequest, ToolResponse
from .erp.tools import ERPToolExecutor
from .extract.tools import ExtractToolExecutor
from .ingest.tools import IngestToolExecutor
from .memory.tools import MemoryToolExecutor
from .orchestrator.tools import OrchestratorToolExecutor
from .planner.tools import PlannerToolExecutor
from .quotes.tools import QuoteToolExecutor


def tool_executor_for(tool_name: str, config: RuntimeConfig) -> object:
    if tool_name.startswith("extract."):
        return ExtractToolExecutor.from_runtime_config(config)
    if tool_name.startswith("erp."):
        return ERPToolExecutor.from_runtime_config(config)
    if tool_name.startswith("ingest."):
        return IngestToolExecutor.from_runtime_config(config)
    if tool_name.startswith("memory."):
        return MemoryToolExecutor.from_runtime_config(config)
    if tool_name.startswith("orchestrator."):
        return OrchestratorToolExecutor.from_runtime_config(config)
    if tool_name.startswith("planner."):
        return PlannerToolExecutor.from_runtime_config(config)
    if tool_name.startswith("quotes."):
        return QuoteToolExecutor.from_runtime_config(config)
    raise ValueError(f"Unsupported tool family for {tool_name}")


def execute_tool_request(
    *,
    config: RuntimeConfig,
    request: ToolRequest,
    source: RequestSource,
    write_approval_artifacts: bool,
    operator_id: str | None = None,
) -> ToolResponse:
    control_plane = ControlPlaneStore.from_runtime_config(config)
    control_plane.record_request_start(
        request=request,
        source=source,
        operator_id=operator_id,
    )
    job_id = control_plane.start_job(
        request_id=request.request_id,
        job_kind=request.tool_name,
        summary={"tool_name": request.tool_name, "dry_run": request.dry_run},
    )
    control_plane.record_job_event(
        job_id=job_id,
        request_id=request.request_id,
        event_type="request_received",
        payload={"tool_name": request.tool_name, "source": source},
    )

    try:
        response = tool_executor_for(request.tool_name, config).execute(request)
    except Exception as exc:
        control_plane.record_job_event(
            job_id=job_id,
            request_id=request.request_id,
            event_type="execution_failed",
            payload={"message": str(exc)},
        )
        control_plane.record_request_internal_error(
            request_id=request.request_id,
            message=str(exc),
        )
        control_plane.finish_job(
            job_id=job_id,
            status=JobStatus.FAILED,
            summary={"message": str(exc)},
        )
        raise

    control_plane.record_job_event(
        job_id=job_id,
        request_id=request.request_id,
        event_type="tool_executed",
        payload={"status": response.status, "tool_name": response.tool_name},
    )
    if write_approval_artifacts and response.approval is not None:
        approval_dir = ApprovalStore(
            config.paths.approvals_dir,
            control_plane=control_plane,
        ).write(response, request_id=request.request_id)
        control_plane.record_job_event(
            job_id=job_id,
            request_id=request.request_id,
            event_type="approval_artifacts_written",
            payload={"approval_dir": str(approval_dir)},
        )
    elif response.approval is not None:
        control_plane.record_review(
            review_id=response.approval.approval_id,
            request_id=request.request_id,
            review_kind=response.approval.action,
            status=_review_status_for_response(response.status),
            target=response.approval.target,
            target_summary=response.approval.summary,
        )

    if (
        request.tool_name
        in {
            "erp.create_draft_quotation",
            "erp.update_draft_quotation",
            "erp.create_draft_purchase_invoice",
            "erp.attach_file",
        }
        and response.status == ToolExecutionStatus.SUCCESS
    ):
        control_plane.record_idempotency_result(
            key=request.request_id,
            scope=f"tool:{request.tool_name}",
            request_id=request.request_id,
            result_fingerprint=sha256(response.to_json_text().encode("utf-8")).hexdigest(),
            retention_marker="erp-write" if not request.dry_run else "dry-run",
        )

    control_plane.record_request_finish(response=response)
    control_plane.finish_job(
        job_id=job_id,
        status=_job_status_for_response(response.status),
        summary={"status": response.status, "tool_name": response.tool_name},
    )
    return response


def _job_status_for_response(status: ToolExecutionStatus) -> JobStatus:
    if status == ToolExecutionStatus.SUCCESS:
        return JobStatus.SUCCESS
    if status == ToolExecutionStatus.APPROVAL_REQUIRED:
        return JobStatus.APPROVAL_REQUIRED
    return JobStatus.FAILED


def _review_status_for_response(status: ToolExecutionStatus):
    from .control_plane.models import ReviewStatus

    if status == ToolExecutionStatus.APPROVAL_REQUIRED:
        return ReviewStatus.PENDING
    return ReviewStatus.ACCEPTED
