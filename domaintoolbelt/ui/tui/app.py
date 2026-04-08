from __future__ import annotations

from collections.abc import Iterable

from domaintoolbelt.core.events import WorkflowEvent
from domaintoolbelt.core.types import WorkflowContext


def render_workflow(
    context: WorkflowContext,
    events: Iterable[WorkflowEvent] = (),
) -> str:
    lines = [f"Session: {context.session_id}", f"Request: {context.request}"]
    if context.master_plan:
        lines.extend(["", context.master_plan])
    if context.guardrail_notes:
        lines.append("")
        lines.append("Guardrails:")
        lines.extend(f"- {note}" for note in context.guardrail_notes)
    if context.completed_steps:
        lines.append("")
        lines.append("Completed steps:")
        for step in context.completed_steps:
            lines.append(f"- {step.step_id}: {step.description} via {step.tool_name}")
    rendered_events = list(events)
    if rendered_events:
        lines.append("")
        lines.append("Recent events:")
        for event in rendered_events[-5:]:
            lines.append(f"- {event.event_type} at {event.created_at}")
    return "\n".join(lines)
