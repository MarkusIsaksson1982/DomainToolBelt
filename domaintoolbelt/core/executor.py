from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from domaintoolbelt.core.events import EventBus, StepCompletedEvent, StepFailedEvent, StepStartedEvent
from domaintoolbelt.core.dependency_graph import DependencyResolver
from domaintoolbelt.core.types import PlanStep, StepOutcome, StepStatus, WorkflowContext


class ParallelExecutor:
    def __init__(self) -> None:
        self.resolver = DependencyResolver()

    def ready_steps(
        self,
        pending_steps: list[PlanStep],
        completed_steps: list[StepOutcome],
        max_parallel_steps: int,
    ) -> list[PlanStep]:
        completed_ids = {result.step_id for result in completed_steps}
        ready = [
            step
            for step in pending_steps
            if all(dependency in completed_ids for dependency in step.depends_on)
        ]
        return ready[:max_parallel_steps]

    async def run_steps(
        self,
        pack: Any,
        steps: list[PlanStep],
        selector: Any,
        validator: Any,
        ctx: WorkflowContext,
        event_bus: EventBus | None = None,
    ) -> list[StepOutcome]:
        tasks = [
            self._run_single_step(pack, step, selector, validator, ctx, event_bus)
            for step in steps
        ]
        return await asyncio.gather(*tasks)

    async def _run_single_step(
        self,
        pack: Any,
        step: PlanStep,
        selector: Any,
        validator: Any,
        ctx: WorkflowContext,
        event_bus: EventBus | None = None,
    ) -> StepOutcome:
        step.status = StepStatus.RUNNING
        selected_tools = await selector.select(
            step.instruction,
            top_k=pack.config.tool_registry.max_tools_per_step,
            preferred=step.preferred_tools,
        )
        if event_bus:
            await event_bus.emit(
                StepStartedEvent(
                    event_type="step_started",
                    session_id=ctx.session_id,
                    step_id=step.step_id,
                    description=step.description,
                    tool_candidates=tuple(selected_tools),
                )
            )
        tool_name = step.tool_name or (selected_tools[0] if selected_tools else None)
        if not tool_name:
            raise ValueError(f"No tool could be selected for step '{step.step_id}'.")

        resolved_args = self._resolve_arg_references(step.tool_args, ctx.completed_steps)
        instruction = self._build_instruction(step, ctx, resolved_args)
        try:
            result = await validator.run_with_validation(
                pack,
                tool_name,
                instruction,
                resolved_args,
                candidate_tools=tuple(selected_tools),
            )
            step.status = StepStatus.COMPLETE
            outcome = StepOutcome(
                step_id=step.step_id,
                description=step.description,
                tool_name=result["tool_name"],
                instruction=instruction,
                output=result["output"],
                citations=result["citations"],
                issues=result.get("issues", ()),
                metadata={
                    "selected_tools": selected_tools,
                    "resolved_args": dict(resolved_args),
                    "attempts": result.get("attempts", 1),
                    **dict(result.get("metadata", {})),
                },
            )
            if event_bus:
                await event_bus.emit(
                    StepCompletedEvent(
                        event_type="step_completed",
                        session_id=ctx.session_id,
                        step_id=step.step_id,
                        tool_name=outcome.tool_name,
                        citations=outcome.citations,
                        issues=outcome.issues,
                    )
                )
            return outcome
        except Exception as exc:
            step.status = StepStatus.FAILED
            if event_bus:
                await event_bus.emit(
                    StepFailedEvent(
                        event_type="step_failed",
                        session_id=ctx.session_id,
                        step_id=step.step_id,
                        error=str(exc),
                    )
                )
            raise

    @staticmethod
    def _build_instruction(
        step: PlanStep,
        ctx: WorkflowContext,
        resolved_args: Mapping[str, Any],
    ) -> str:
        lines = [step.instruction]
        if resolved_args:
            lines.append("")
            lines.append("Resolved inputs:")
            for key, value in resolved_args.items():
                lines.append(f"- {key}: {ParallelExecutor._stringify(value)}")

        if ctx.retrieved_context:
            lines.append("")
            lines.append("Retrieved context:")
            for item in ctx.retrieved_context[:3]:
                lines.append(f"- {item}")

        if ctx.memory_context:
            lines.append("")
            lines.append("Relevant prior memory:")
            for item in ctx.memory_context[:2]:
                lines.append(f"- {item}")

        return "\n".join(lines)

    @staticmethod
    def _resolve_arg_references(
        arguments: Mapping[str, Any],
        completed_steps: list[StepOutcome],
    ) -> dict[str, Any]:
        context = {result.step_id: result.output for result in completed_steps}
        resolved: dict[str, Any] = {}
        for key, value in arguments.items():
            if isinstance(value, str) and value.startswith("$"):
                reference, _, field_name = value[1:].partition(".")
                output = context.get(reference)
                if field_name and isinstance(output, Mapping):
                    resolved[key] = output.get(field_name)
                else:
                    resolved[key] = output
            else:
                resolved[key] = value
        return resolved

    @staticmethod
    def _stringify(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return ", ".join(ParallelExecutor._stringify(item) for item in value)
        if isinstance(value, Mapping):
            return ", ".join(f"{key}={ParallelExecutor._stringify(item)}" for key, item in value.items())
        return str(value)
