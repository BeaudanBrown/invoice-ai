from __future__ import annotations

from ..config import RuntimeConfig
from ..erp.schemas import ToolRequest, ToolResponse
from ..orchestrator.tools import OrchestratorToolExecutor
from .engine import PlannerEngine
from .models import PlannerTurn
from .parser import PlannerParseError


class PlannerToolExecutor:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.orchestrator = OrchestratorToolExecutor.from_runtime_config(config)
        self.engine = PlannerEngine(config=config)

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
        except PlannerParseError as exc:
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
        orchestrator_request = ToolRequest(
            request_id=request.request_id,
            tool_name="orchestrator.handle_request",
            dry_run=request.dry_run,
            payload=operator_request,
            conversation_context=request.conversation_context,
        )
        orchestrated = self.orchestrator.execute(orchestrator_request)
        return ToolResponse(
            request_id=request.request_id,
            tool_name=request.tool_name,
            status=orchestrated.status,
            data={
                "request_kind": operator_request.get("request_kind"),
                "planned_request": operator_request,
                "planner_contract": planned.data["planner_contract"],
                "memory_context": planned.data.get("memory_context", {}),
                "planning_source": planned.data.get("planning_source"),
                "model_details": planned.data.get("model_details", {}),
                "stage": orchestrated.data.get("stage"),
                "artifacts": orchestrated.data.get("artifacts", []),
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
