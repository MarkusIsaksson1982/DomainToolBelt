from __future__ import annotations

from domaintoolbelt.core.types import PlanStep, ToolSpec, WorkflowContext


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
        tools = {tool.name: tool for tool in pack.config.tools}
        primary_tool = self._select_primary_tool(pack.config.tools)

        steps = [
            PlanStep(
                step_id="step-1",
                description="Gather the most relevant primary sources.",
                instruction=f"Retrieve the strongest primary sources for: {ctx.request}",
                preferred_tools=(primary_tool.name,),
                tool_args={"query": ctx.request},
            )
        ]

        if "cross_reference" in tools:
            steps.append(
                PlanStep(
                    step_id="step-2",
                    description="Find cross references that reinforce or clarify the primary sources.",
                    instruction=f"Find grounded cross references that speak to: {ctx.request}",
                    depends_on=("step-1",),
                    tool_name="cross_reference",
                    tool_args={"seed_summary": "$step-1.summary"},
                )
            )

        if "theme_summary" in tools:
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
                    tool_name="theme_summary",
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
