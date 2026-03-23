from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from ..config import RuntimeConfig


class PlannerOllamaError(RuntimeError):
    pass


class OllamaPlannerAssistant:
    def __init__(self, *, base_url: str, model: str, timeout_seconds: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_runtime_config(
        cls,
        config: RuntimeConfig,
        *,
        model: str,
    ) -> "OllamaPlannerAssistant":
        return cls(base_url=config.dependencies.ollama_url, model=model)

    def plan_request(
        self,
        *,
        message: str,
        defaults: dict[str, Any],
        conversation_context: dict[str, Any],
        memory_context: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = _planner_prompt(
            message=message,
            defaults=defaults,
            conversation_context=conversation_context,
            memory_context=memory_context,
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        req = request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise PlannerOllamaError(str(exc.reason)) from exc
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise PlannerOllamaError(body or str(exc)) from exc

        raw_text = response_payload.get("response")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise PlannerOllamaError("Ollama did not return a planner response payload")

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise PlannerOllamaError("Ollama returned invalid planner JSON") from exc
        if not isinstance(parsed, dict):
            raise PlannerOllamaError("Ollama planner response must be a JSON object")
        return parsed


def _planner_prompt(
    *,
    message: str,
    defaults: dict[str, Any],
    conversation_context: dict[str, Any],
    memory_context: dict[str, Any],
) -> str:
    return (
        "You are a planner for invoice-ai. Convert the operator turn into one safe structured "
        "operator request. Only produce JSON.\n"
        "Supported request kinds: supplier_document_intake, quote_draft, quote_revision.\n"
        "Do not invent ERP writes directly. Output exactly one JSON object shaped as an "
        "operator request for orchestrator.handle_request.\n"
        "If revising a quote, preserve draft_key/quotation from conversation_context.active_quote "
        "when available.\n"
        "If the request is unsupported or too ambiguous, output "
        '{"request_kind":"unsupported","reason":"..."}' "\n\n"
        f"message:\n{message}\n\n"
        f"defaults:\n{json.dumps(defaults, indent=2, sort_keys=True)}\n\n"
        f"conversation_context:\n{json.dumps(conversation_context, indent=2, sort_keys=True)}\n\n"
        f"memory_context:\n{json.dumps(memory_context, indent=2, sort_keys=True)}\n"
    )
