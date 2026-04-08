from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager
from typing import Any

from domaintoolbelt.core.events import (
    EventBus,
    PlanCreatedEvent,
    ReviewRequiredEvent,
    StepCompletedEvent,
    StepFailedEvent,
    StepStartedEvent,
    ValidationWarningEvent,
    WorkflowCompletedEvent,
    WorkflowEvent,
)


class RichWorkflowRenderer(AbstractContextManager["RichWorkflowRenderer"]):
    def __init__(self, request: str) -> None:
        try:
            from rich.console import Console
            from rich.live import Live
        except ImportError as exc:
            raise ImportError(
                "RichWorkflowRenderer requires the optional 'rich' package. "
                "Install with: pip install domaintoolbelt[tui]"
            ) from exc
        self.console = Console()
        self._live_type = Live
        self.request = request
        self.step_status: dict[str, str] = {}
        self.recent_events: list[str] = []
        self.master_plan = ""
        self.warnings: list[str] = []
        self.review_reason = ""
        self.final_answer = ""
        self._live = None

    def attach(self, event_bus: EventBus) -> None:
        event_bus.subscribe(self._on_event)

    def __enter__(self) -> "RichWorkflowRenderer":
        self._live = self._live_type(self.renderable(), console=self.console, refresh_per_second=8)
        self._live.__enter__()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self._live:
            self._live.__exit__(exc_type, exc, exc_tb)
        self._live = None

    def _on_event(self, event: WorkflowEvent) -> None:
        self._remember_event(event)
        if isinstance(event, PlanCreatedEvent):
            self.master_plan = event.master_plan
            for step_id in event.step_ids:
                self.step_status.setdefault(step_id, "pending")
        elif isinstance(event, StepStartedEvent):
            self.step_status[event.step_id] = f"running via {', '.join(event.tool_candidates[:2])}"
        elif isinstance(event, StepCompletedEvent):
            self.step_status[event.step_id] = f"done via {event.tool_name}"
        elif isinstance(event, StepFailedEvent):
            self.step_status[event.step_id] = f"failed: {event.error}"
        elif isinstance(event, ValidationWarningEvent):
            self.warnings.append(f"{event.phase}: {event.message}")
        elif isinstance(event, ReviewRequiredEvent):
            self.review_reason = event.reason
        elif isinstance(event, WorkflowCompletedEvent):
            self.final_answer = event.final_answer

        if self._live:
            self._live.update(self.renderable())

    def renderable(self) -> Any:
        from rich.console import Group
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        step_table = Table(expand=True)
        step_table.add_column("Step")
        step_table.add_column("Status")
        for step_id, status in self.step_status.items():
            step_table.add_row(step_id, status)

        event_lines = Text("\n".join(self.recent_events[-8:]) or "Waiting for events...")
        warnings = Text("\n".join(self.warnings[-4:]) or "None")
        final = Text(self.final_answer or "In progress...")

        panels = [
            Panel(Text(self.request), title="Request"),
            Panel(Text(self.master_plan or "Planning..."), title="Plan"),
            Panel(step_table, title="Steps"),
            Panel(event_lines, title="Recent Events"),
            Panel(warnings, title="Warnings"),
        ]
        if self.review_reason:
            panels.append(Panel(Text(self.review_reason), title="Review Required"))
        if self.final_answer:
            panels.append(Panel(final, title="Final Answer"))
        return Group(*panels)

    def _remember_event(self, event: WorkflowEvent) -> None:
        detail = event.event_type
        if hasattr(event, "step_id") and getattr(event, "step_id"):
            detail += f" ({getattr(event, 'step_id')})"
        self.recent_events.append(f"{event.created_at} {detail}")
