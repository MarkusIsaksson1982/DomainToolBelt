from __future__ import annotations

from domaintoolbelt.core.types import WorkflowContext


def render_workflow(context: WorkflowContext) -> str:
    lines = [f"Session: {context.session_id}", f"Request: {context.request}"]
    if context.master_plan:
        lines.extend(["", context.master_plan])
    if context.completed_steps:
        lines.append("")
        lines.append("Completed steps:")
        for step in context.completed_steps:
            lines.append(f"- {step.step_id}: {step.description} via {step.tool_name}")
    return "\n".join(lines)
