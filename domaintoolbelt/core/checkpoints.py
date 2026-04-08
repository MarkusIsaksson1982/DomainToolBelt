from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from domaintoolbelt.core.types import FinalAnswer, PlanStep, StepOutcome, StepStatus, WorkflowContext


class CheckpointStore:
    def __init__(self, root: str | Path = ".domaintoolbelt/checkpoints"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, context: Any) -> Path:
        path = self.root / f"{context.session_id}.json"
        payload = self._serialize(context)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load(self, session_id: str) -> dict[str, Any]:
        path = self.root / f"{session_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def restore(self, session_id: str) -> WorkflowContext:
        payload = self.load(session_id)
        ctx = WorkflowContext(
            request=payload["request"],
            session_id=payload.get("session_id", session_id),
            master_plan=payload.get("master_plan", ""),
            retrieved_context=list(payload.get("retrieved_context", [])),
            memory_context=list(payload.get("memory_context", [])),
            guardrail_notes=list(payload.get("guardrail_notes", [])),
            final_answer=payload.get("final_answer", ""),
        )
        ctx.plan = [_coerce_plan_step(step) for step in payload.get("plan", [])]
        ctx.completed_steps = [
            _coerce_step_outcome(step) for step in payload.get("completed_steps", [])
        ]
        ctx.grounding_report = payload.get("grounding_report")
        final_payload = payload.get("final_payload")
        if isinstance(final_payload, dict):
            ctx.final_payload = _coerce_final_answer(final_payload)
        return ctx

    def _serialize(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._serialize(asdict(value))
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._serialize(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        return value


def _coerce_plan_step(payload: dict[str, Any]) -> PlanStep:
    return PlanStep(
        step_id=str(payload["step_id"]),
        description=str(payload["description"]),
        instruction=str(payload["instruction"]),
        depends_on=tuple(str(item) for item in payload.get("depends_on", [])),
        preferred_tools=tuple(str(item) for item in payload.get("preferred_tools", [])),
        tool_name=str(payload["tool_name"]) if payload.get("tool_name") else None,
        tool_args=dict(payload.get("tool_args", {})),
        status=StepStatus(payload.get("status", StepStatus.PENDING.value)),
    )


def _coerce_step_outcome(payload: dict[str, Any]) -> StepOutcome:
    return StepOutcome(
        step_id=str(payload["step_id"]),
        description=str(payload["description"]),
        tool_name=str(payload["tool_name"]),
        instruction=str(payload["instruction"]),
        output=payload.get("output"),
        citations=tuple(str(item) for item in payload.get("citations", [])),
        issues=tuple(str(item) for item in payload.get("issues", [])),
        metadata=dict(payload.get("metadata", {})),
    )


def _coerce_final_answer(payload: dict[str, Any]) -> FinalAnswer:
    confidence = payload.get("confidence")
    if confidence is not None:
        confidence = float(confidence)
    return FinalAnswer(
        answer=str(payload.get("answer", "")),
        citations=tuple(str(item) for item in payload.get("citations", [])),
        confidence=confidence,
        issues=tuple(str(item) for item in payload.get("issues", [])),
        metadata=dict(payload.get("metadata", {})),
    )
