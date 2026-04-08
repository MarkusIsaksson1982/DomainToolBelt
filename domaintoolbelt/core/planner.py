from __future__ import annotations

from collections.abc import Mapping
import inspect
from typing import Any

from domaintoolbelt.domain_packs.base import has_prompts
from domaintoolbelt.core.types import PlanStep, ToolSpec, WorkflowContext
from domaintoolbelt.llm.provider import LLMProvider, ProviderConfig, StructuredOutputError


class HeuristicPlanner:
    """A deterministic baseline planner for starter repositories and tests."""

    async def create_plan(self, pack, ctx: WorkflowContext) -> str:
        intent = ""
        if hasattr(pack, "disambiguate_intent"):
            try:
                intent = pack.disambiguate_intent(ctx.request)
            except NotImplementedError:
                intent = ""

        steps = await self.expand_plan(pack, ctx)
        numbered = "\n".join(f"{index + 1}. {step.description}" for index, step in enumerate(steps))
        if intent:
            return f"Intent: {intent}\n\nPlan:\n{numbered}"
        return f"Plan:\n{numbered}"

    async def expand_plan(self, pack, ctx: WorkflowContext) -> list[PlanStep]:
        primary_tool = self._select_primary_tool(pack.config.tools)
        secondary_tool = self._select_supporting_tool(pack.config.tools)
        synthesis_tool = self._select_synthesis_tool(pack.config.tools)

        steps = [
            PlanStep(
                step_id="step-1",
                description="Gather the most relevant primary sources.",
                instruction=f"Retrieve the strongest primary sources for: {ctx.request}",
                preferred_tools=(primary_tool.name,),
                tool_args={"query": ctx.request},
            )
        ]

        if secondary_tool:
            steps.append(
                PlanStep(
                    step_id="step-2",
                    description="Find cross references that reinforce or clarify the primary sources.",
                    instruction=f"Find grounded cross references that speak to: {ctx.request}",
                    depends_on=("step-1",),
                    tool_name=secondary_tool.name,
                    tool_args={"seed_summary": "$step-1.summary"},
                )
            )

        if synthesis_tool:
            dependencies = tuple(step.step_id for step in steps)
            tool_args = {"primary": "$step-1.summary"}
            if len(steps) > 1:
                tool_args["secondary"] = "$step-2.summary"
            steps.append(
                PlanStep(
                    step_id="step-3",
                    description="Synthesize a domain-grounded summary from the gathered evidence.",
                    instruction=f"Write a concise, citation-rich synthesis for: {ctx.request}",
                    depends_on=dependencies,
                    tool_name=synthesis_tool.name,
                    tool_args=tool_args,
                )
            )

        return steps

    @staticmethod
    def _select_primary_tool(tools: tuple[ToolSpec, ...]) -> ToolSpec:
        authoritative = [tool for tool in tools if tool.authoritative]
        if authoritative:
            return authoritative[0]
        if tools:
            return tools[0]
        raise ValueError("Domain pack must define at least one tool.")

    @staticmethod
    def _select_supporting_tool(tools: tuple[ToolSpec, ...]) -> ToolSpec | None:
        for tool in tools:
            if tool.name == "cross_reference" or any(
                tag in {"cross", "reference", "related", "secondary"} for tag in tool.tags
            ):
                return tool
        return None

    @staticmethod
    def _select_synthesis_tool(tools: tuple[ToolSpec, ...]) -> ToolSpec | None:
        for tool in tools:
            if tool.name == "theme_summary" or any(
                tag in {"summary", "synthesis", "theme"} for tag in tool.tags
            ):
                return tool
        return None


class LLMPlanner(HeuristicPlanner):
    def __init__(self, provider: LLMProvider | None = None, warning_callback=None) -> None:
        self.provider = provider
        self.warning_callback = warning_callback

    async def create_plan(self, pack, ctx: WorkflowContext) -> str:
        if not (self.provider and has_prompts(pack) and pack.config.llm.enabled):
            return await super().create_plan(pack, ctx)

        steps = await self.expand_plan(pack, ctx)
        if pack.config.llm.structured_output:
            intent = ""
            if hasattr(pack, "disambiguate_intent"):
                try:
                    intent = pack.disambiguate_intent(ctx.request)
                except NotImplementedError:
                    intent = ""
            numbered = "\n".join(f"{index + 1}. {step.description}" for index, step in enumerate(steps))
            if intent:
                return f"Intent: {intent}\n\nPlan:\n{numbered}"
            return f"Plan:\n{numbered}"

        prompt = pack.load_prompt("create_action_plan.md", request=ctx.request)
        prompt += (
            "\n\nReturn a short human-readable plan summary that respects the following step list:\n"
            + "\n".join(f"- {step.description}" for step in steps)
        )
        try:
            response = await self.provider.complete(
                prompt,
                system=_load_optional_prompt(pack, "supervisor.md"),
                config=_provider_config(pack.config.llm.planner_model, pack),
            )
        except Exception:
            return await super().create_plan(pack, ctx)

        cleaned = response.strip()
        if not cleaned:
            return await super().create_plan(pack, ctx)
        return cleaned

    async def expand_plan(self, pack, ctx: WorkflowContext) -> list[PlanStep]:
        if not (self.provider and has_prompts(pack) and pack.config.llm.enabled):
            return await super().expand_plan(pack, ctx)

        prompt = pack.load_prompt("create_action_plan.md", request=ctx.request)
        prompt += (
            "\n\nAvailable tools:\n"
            + "\n".join(f"- {tool.name}: {tool.description}" for tool in pack.config.tools)
            + "\n\nReturn a JSON array of plan steps. Each item must contain:\n"
            'step_id, description, instruction, depends_on, preferred_tools, tool_name, tool_args.\n'
            "Use an empty string for tool_name if the selector should choose the tool."
        )
        schema = {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_id": {"type": "string"},
                            "description": {"type": "string"},
                            "instruction": {"type": "string"},
                            "depends_on": {"type": "array", "items": {"type": "string"}},
                            "preferred_tools": {"type": "array", "items": {"type": "string"}},
                            "tool_name": {"type": "string"},
                            "tool_args": {"type": "object"},
                        },
                        "required": ["step_id", "description", "instruction"],
                    },
                }
            },
            "required": ["steps"],
        }
        try:
            response = await self.provider.structured(
                prompt,
                schema=schema,
                system=_load_optional_prompt(pack, "supervisor.md"),
                config=_provider_config(
                    pack.config.llm.planner_model,
                    pack,
                    response_format="json_object",
                ),
            )
            steps = _coerce_plan_steps(response, pack.config.tools)
        except (StructuredOutputError, ValueError, TypeError):
            await self._emit_warning(
                ctx,
                "planner",
                "Planner structured output was invalid; falling back to the heuristic plan.",
            )
            return await super().expand_plan(pack, ctx)
        except Exception:
            await self._emit_warning(
                ctx,
                "planner",
                "Planner LLM call failed; falling back to the heuristic plan.",
            )
            return await super().expand_plan(pack, ctx)

        return steps or await super().expand_plan(pack, ctx)

    async def _emit_warning(self, ctx: WorkflowContext, phase: str, message: str) -> None:
        if not self.warning_callback:
            return
        result = self.warning_callback(ctx, phase, message)
        if inspect.isawaitable(result):
            await result


def _coerce_plan_steps(payload: Any, tools: tuple[ToolSpec, ...]) -> list[PlanStep]:
    if isinstance(payload, Mapping):
        payload = payload.get("steps", [])
    if not isinstance(payload, list):
        raise ValueError("Planner response must be a list of steps.")

    allowed = {tool.name for tool in tools}
    steps: list[PlanStep] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise ValueError("Planner step entries must be mappings.")

        step_id = str(item.get("step_id") or f"step-{index + 1}")
        description = str(item.get("description") or "").strip()
        instruction = str(item.get("instruction") or "").strip()
        if not description or not instruction:
            raise ValueError("Planner steps must include description and instruction.")

        depends_on = tuple(str(value) for value in _iter_strings(item.get("depends_on")))
        preferred_tools = tuple(
            value for value in _iter_strings(item.get("preferred_tools")) if value in allowed
        )
        tool_name = str(item.get("tool_name") or "").strip() or None
        if tool_name and tool_name not in allowed:
            tool_name = None
        raw_args = item.get("tool_args", {})
        tool_args = dict(raw_args) if isinstance(raw_args, Mapping) else {}

        steps.append(
            PlanStep(
                step_id=step_id,
                description=description,
                instruction=instruction,
                depends_on=depends_on,
                preferred_tools=preferred_tools,
                tool_name=tool_name,
                tool_args=tool_args,
            )
        )
    return steps


def _iter_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _load_optional_prompt(pack: Any, filename: str) -> str | None:
    if not has_prompts(pack):
        return None
    try:
        return pack.load_prompt(filename)
    except FileNotFoundError:
        return None


def _provider_config(model_name: str, pack: Any, response_format: str | None = None) -> ProviderConfig:
    return ProviderConfig(
        model=model_name,
        temperature=pack.config.llm.temperature,
        max_tokens=pack.config.llm.max_tokens,
        response_format=response_format,
        metadata={"pack": pack.config.key},
    )
