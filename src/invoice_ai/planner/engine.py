from __future__ import annotations

from typing import Any

from pydantic import Field

from ..config import RuntimeConfig
from ..modeling import InvoiceAIModel
from ..memory.store import MemoryStore
from .models import PlannerTurn
from .ollama import OllamaPlannerAssistant, PlannerOllamaError
from .parser import PlannerParseError, plan_operator_request
from .suggestions import infer_memory_suggestions


class PlannerOutcome(InvoiceAIModel):
    operator_request: dict[str, Any]
    planning_source: str
    memory_context: dict[str, Any]
    memory_suggestions: tuple[dict[str, Any], ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    model_details: dict[str, Any] = Field(default_factory=dict)


class PlannerEngine:
    def __init__(self, *, config: RuntimeConfig) -> None:
        self.config = config
        self.memory = MemoryStore(config.paths.memory_dir)

    def plan(self, turn: PlannerTurn) -> PlannerOutcome:
        memory_context = self.memory.planning_context(
            message=turn.message,
            defaults=turn.defaults,
            conversation_context=turn.conversation_context,
        )
        merged_defaults = dict(memory_context.get("merged_defaults", turn.defaults))
        memory_enriched_turn = PlannerTurn(
            request_id=turn.request_id,
            message=turn.message,
            attachments=turn.attachments,
            defaults=merged_defaults,
            conversation_context=turn.conversation_context,
        )

        warnings: list[str] = []
        planner_defaults = dict(merged_defaults.get("planner", {}))
        use_model_assist = bool(planner_defaults.get("use_model_assist", False))
        model_name = planner_defaults.get("model")

        if use_model_assist and model_name:
            try:
                operator_request = OllamaPlannerAssistant.from_runtime_config(
                    self.config,
                    model=str(model_name),
                ).plan_request(
                    message=turn.message,
                    defaults=merged_defaults,
                    conversation_context=turn.conversation_context,
                    memory_context=memory_context,
                )
                if operator_request.get("request_kind") == "unsupported":
                    raise PlannerParseError(
                        str(operator_request.get("reason") or "Model could not classify the turn")
                    )
                return PlannerOutcome(
                    operator_request=operator_request,
                    planning_source="model_assist",
                    memory_context=memory_context,
                    memory_suggestions=tuple(
                        suggestion.as_dict()
                        for suggestion in infer_memory_suggestions(
                            turn=memory_enriched_turn,
                            operator_request=operator_request,
                        )
                    ),
                    warnings=tuple(warnings),
                    model_details={"model": str(model_name), "provider": "ollama"},
                )
            except (PlannerOllamaError, PlannerParseError, ValueError) as exc:
                warnings.append(f"Model-assisted planning failed, falling back to heuristics: {exc}")
        elif use_model_assist and not model_name:
            warnings.append("Model-assisted planning requested but defaults.planner.model is missing")

        operator_request = plan_operator_request(memory_enriched_turn)
        return PlannerOutcome(
            operator_request=operator_request,
            planning_source="heuristic",
            memory_context=memory_context,
            memory_suggestions=tuple(
                suggestion.as_dict()
                for suggestion in infer_memory_suggestions(
                    turn=memory_enriched_turn,
                    operator_request=operator_request,
                )
            ),
            warnings=tuple(warnings),
            model_details={},
        )
