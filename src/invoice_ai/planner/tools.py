from __future__ import annotations

from pydantic import ValidationError

from ..approvals.store import ApprovalStore
from ..config import RuntimeConfig
from ..erp.schemas import ToolRequest, ToolResponse
from ..memory.tools import MemoryToolExecutor
from ..orchestrator.tools import OrchestratorToolExecutor
from .engine import PlannerEngine
from .models import PlannerTurn
from .parser import PlannerParseError


class PlannerToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.approvals = ApprovalStore(config.paths.approvals_dir)
        self.engine = PlannerEngine(config=config)
        self._memory: MemoryToolExecutor | None = None
        self._orchestrator: OrchestratorToolExecutor | None = None

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "PlannerToolExecutor":
        return cls(config=config)

    def execute(self, request: ToolRequest) -> ToolResponse:
        handlers = {
            "planner.plan_turn": self.plan_turn,
            "planner.handle_turn": self.handle_turn,
        }
        handler = handlers.get(request.tool_name)
        if handler is None:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="blocked",
                errors=[
                    {
                        "code": "planner.unsupported_tool",
                        "message": f"Unsupported planner tool: {request.tool_name}",
                    }
                ],
            )
        return handler(request)

    def plan_turn(self, request: ToolRequest) -> ToolResponse:
        turn = PlannerTurn.from_payload(
            request.request_id,
            request.payload,
            conversation_context=request.conversation_context,
        )
        try:
            outcome = self.engine.plan(turn)
        except (PlannerParseError, ValidationError, ValueError) as exc:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[
                    {
                        "code": "planner.unhandled_turn",
                        "message": str(exc),
                    }
                ],
            )

        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status="success",
            data={
                "planner_message": turn.message,
                "request_kind": outcome.operator_request.get("request_kind"),
                "operator_request": outcome.operator_request,
                "memory_context": outcome.memory_context,
                "memory_suggestions": list(outcome.memory_suggestions),
                "planning_source": outcome.planning_source,
                "model_details": outcome.model_details,
                "planner_contract": {
                    "contract_version": "structured-v1",
                    "next_tool": "orchestrator.handle_request",
                },
            },
            warnings=list(outcome.warnings),
        )

    def handle_turn(self, request: ToolRequest) -> ToolResponse:
        planned = self.plan_turn(request)
        if planned.status != "success":
            return planned

        operator_request = dict(planned.data["operator_request"])
        planned_memory_suggestions = list(planned.data.get("memory_suggestions", []))
        if operator_request.get("request_kind") == "memory_suggestion":
            return self._handle_memory_suggestion_turn(
                request=request,
                planned=planned,
                memory_suggestions=planned_memory_suggestions,
            )

        orchestrator_request = ToolRequest(
            request_id=request.request_id,
            tool_name="orchestrator.handle_request",
            dry_run=request.dry_run,
            payload=operator_request,
            conversation_context=request.conversation_context,
        )
        orchestrated = self.orchestrator.execute(orchestrator_request)
        memory_reviews = self._memory_reviews(
            request=request,
            memory_suggestions=planned_memory_suggestions,
        )
        artifacts = list(orchestrated.data.get("artifacts", []))
        for review in memory_reviews:
            artifacts.extend(review.get("artifacts", []))
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=orchestrated.status,
            data={
                "request_kind": operator_request.get("request_kind"),
                "planned_request": operator_request,
                "planner_contract": planned.data["planner_contract"],
                "memory_context": planned.data.get("memory_context", {}),
                "memory_suggestions": planned_memory_suggestions,
                "memory_reviews": memory_reviews,
                "planning_source": planned.data.get("planning_source"),
                "model_details": planned.data.get("model_details", {}),
                "stage": orchestrated.data.get("stage"),
                "artifacts": artifacts,
                "erp_refs": orchestrated.data.get("erp_refs", []),
                "conversation_state": orchestrated.data.get("conversation_state", {}),
                "orchestrator_response": orchestrated.as_dict(),
            },
            errors=orchestrated.errors,
            warnings=[*planned.warnings, *orchestrated.warnings],
            approval=orchestrated.approval,
            meta={
                **orchestrated.meta,
                "planned_request_kind": operator_request.get("request_kind"),
                "planning_source": planned.data.get("planning_source"),
            },
        )

    def _handle_memory_suggestion_turn(
        self,
        *,
        request: ToolRequest,
        planned: ToolResponse,
        memory_suggestions: list[dict[str, object]],
    ) -> ToolResponse:
        if not memory_suggestions:
            return ToolResponse(
                request_id=request.request_id,
                tool_name=request.tool_name,
                status="validation_error",
                errors=[
                    {
                        "code": "planner.memory_suggestion_missing",
                        "message": "Planner did not infer a memory suggestion from the operator turn",
                    }
                ],
            )

        primary_review = self._memory_reviews(
            request=request,
            memory_suggestions=[memory_suggestions[0]],
        )[0]
        status = str(primary_review.get("status") or "blocked")
        approval_payload = primary_review.get("approval")

        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=status,
            data={
                "request_kind": "memory_suggestion",
                "planned_request": dict(planned.data["operator_request"]),
                "planner_contract": planned.data["planner_contract"],
                "memory_context": planned.data.get("memory_context", {}),
                "memory_suggestions": memory_suggestions,
                "memory_reviews": [primary_review],
                "planning_source": planned.data.get("planning_source"),
                "model_details": planned.data.get("model_details", {}),
                "stage": "memory_review",
                "artifacts": list(primary_review.get("artifacts", [])),
                "erp_refs": [],
                "conversation_state": {},
                "orchestrator_response": None,
            },
            errors=list(primary_review.get("errors", [])),
            warnings=list(primary_review.get("warnings", [])),
            approval=None if approval_payload is None else _approval_from_dict(approval_payload),
            meta={
                "planned_request_kind": "memory_suggestion",
                "planning_source": planned.data.get("planning_source"),
            },
        )

    def _memory_reviews(
        self,
        *,
        request: ToolRequest,
        memory_suggestions: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        reviews: list[dict[str, object]] = []
        for index, suggestion in enumerate(memory_suggestions, start=1):
            response = self.memory.execute(
                ToolRequest(
                    request_id=f"{request.request_id}-memory-{index}",
                    tool_name="memory.suggest_update",
                    dry_run=request.dry_run,
                    payload=suggestion,
                    conversation_context=request.conversation_context,
                )
            )
            review = {
                "tool_name": "memory.suggest_update",
                "status": response.status,
                "suggestion": response.data.get("suggestion"),
                "approval": None if response.approval is None else response.approval.as_dict(),
                "artifacts": [],
                "errors": response.errors,
                "warnings": response.warnings,
            }
            approval = response.approval
            if approval is not None:
                approval_dir = self.approvals.write(response)
                for kind, path in approval.artifacts.as_dict().items():
                    if path is None:
                        continue
                    review["artifacts"].append({"kind": kind, "path": path})
                review["approval_dir"] = str(approval_dir)
            reviews.append(review)
        return reviews

    @property
    def memory(self) -> MemoryToolExecutor:
        if self._memory is None:
            self._memory = MemoryToolExecutor.from_runtime_config(self.config)
        return self._memory

    @property
    def orchestrator(self) -> OrchestratorToolExecutor:
        if self._orchestrator is None:
            self._orchestrator = OrchestratorToolExecutor.from_runtime_config(self.config)
        return self._orchestrator


def _approval_from_dict(payload: dict[str, object]):
    from ..erp.schemas import ApprovalArtifactPaths, ApprovalPayload

    artifacts = dict(payload.get("artifacts", {}))
    return ApprovalPayload(
        approval_id=str(payload["approval_id"]),
        action=str(payload["action"]),
        summary=str(payload["summary"]),
        target=dict(payload.get("target", {})),
        proposed_changes=dict(payload.get("proposed_changes", {})),
        artifacts=ApprovalArtifactPaths(
            summary_markdown_path=None
            if artifacts.get("summary_markdown_path") is None
            else str(artifacts["summary_markdown_path"]),
            request_json_path=None
            if artifacts.get("request_json_path") is None
            else str(artifacts["request_json_path"]),
            diff_json_path=None
            if artifacts.get("diff_json_path") is None
            else str(artifacts["diff_json_path"]),
        ),
    )
