from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from domaintoolbelt.core.types import PlanStep, StepOutcome, StepStatus, WorkflowContext


@dataclass
class ExecutionCluster:
    cluster_id: int
    steps: list[PlanStep]


class DependencyResolver:
    """Resolve plan steps into dependency-safe execution clusters."""

    def resolve(self, steps: list[PlanStep]) -> list[ExecutionCluster]:
        step_map = {step.step_id: step for step in steps}
        dependents: dict[str, set[str]] = {step.step_id: set() for step in steps}
        in_degree: dict[str, int] = {step.step_id: 0 for step in steps}

        for step in steps:
            for dependency in step.depends_on:
                if dependency not in step_map:
                    raise ValueError(f"Unknown dependency '{dependency}' for step '{step.step_id}'.")
                dependents[dependency].add(step.step_id)
                in_degree[step.step_id] += 1

        ready = {step_id for step_id, degree in in_degree.items() if degree == 0}
        clusters: list[ExecutionCluster] = []
        cluster_id = 0

        while ready:
            cluster_steps = [step_map[step_id] for step_id in sorted(ready)]
            clusters.append(ExecutionCluster(cluster_id=cluster_id, steps=cluster_steps))
            cluster_id += 1

            next_ready: set[str] = set()
            for step in cluster_steps:
                for dependent_id in dependents[step.step_id]:
                    in_degree[dependent_id] -= 1
                    if in_degree[dependent_id] == 0:
                        next_ready.add(dependent_id)
            ready = next_ready

        resolved_count = sum(len(cluster.steps) for cluster in clusters)
        if resolved_count != len(steps):
            raise ValueError("Dependency graph has a cycle; cannot resolve execution order.")
        return clusters


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
    ) -> list[StepOutcome]:
        tasks = [self._run_single_step(pack, step, selector, validator, ctx) for step in steps]
        return await asyncio.gather(*tasks)

    async def _run_single_step(
        self,
        pack: Any,
        step: PlanStep,
        selector: Any,
        validator: Any,
        ctx: WorkflowContext,
    ) -> StepOutcome:
        step.status = StepStatus.RUNNING
        selected_tools = await selector.select(
            step.instruction,
            top_k=pack.config.tool_registry.max_tools_per_step,
            preferred=step.preferred_tools,
        )
        tool_name = step.tool_name or (selected_tools[0] if selected_tools else None)
        if not tool_name:
            raise ValueError(f"No tool could be selected for step '{step.step_id}'.")

        resolved_args = self._resolve_arg_references(step.tool_args, ctx.completed_steps)
        instruction = self._build_instruction(step, ctx, resolved_args)
        result = await validator.run_with_validation(pack, tool_name, instruction, resolved_args)
        step.status = StepStatus.COMPLETE

        return StepOutcome(
            step_id=step.step_id,
            description=step.description,
            tool_name=tool_name,
            instruction=instruction,
            output=result["output"],
            citations=result["citations"],
            issues=result.get("issues", ()),
            metadata={
                "selected_tools": selected_tools,
                "resolved_args": dict(resolved_args),
            },
        )

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
