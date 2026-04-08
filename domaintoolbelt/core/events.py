from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import inspect
from typing import Any, Awaitable, Callable


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class WorkflowEvent:
    event_type: str
    session_id: str
    created_at: str = field(default_factory=_timestamp)


@dataclass(frozen=True)
class RunStartedEvent(WorkflowEvent):
    request: str = ""
    pack_key: str = ""


@dataclass(frozen=True)
class RunResumedEvent(WorkflowEvent):
    request: str = ""
    pack_key: str = ""


@dataclass(frozen=True)
class ContextRetrievedEvent(WorkflowEvent):
    retrieved_count: int = 0
    memory_count: int = 0


@dataclass(frozen=True)
class PlanCreatedEvent(WorkflowEvent):
    master_plan: str = ""
    step_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ValidationWarningEvent(WorkflowEvent):
    phase: str = ""
    message: str = ""


@dataclass(frozen=True)
class StepStartedEvent(WorkflowEvent):
    step_id: str = ""
    description: str = ""
    tool_candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepCompletedEvent(WorkflowEvent):
    step_id: str = ""
    tool_name: str = ""
    citations: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class StepFailedEvent(WorkflowEvent):
    step_id: str = ""
    error: str = ""


@dataclass(frozen=True)
class ReviewRequiredEvent(WorkflowEvent):
    step_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class CheckpointSavedEvent(WorkflowEvent):
    path: str = ""


@dataclass(frozen=True)
class WorkflowCompletedEvent(WorkflowEvent):
    final_answer: str = ""


EventHandler = Callable[[WorkflowEvent], Any | Awaitable[Any]]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[EventHandler] = []
        self._history: list[WorkflowEvent] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._subscribers.append(handler)

    @property
    def history(self) -> tuple[WorkflowEvent, ...]:
        return tuple(self._history)

    async def emit(self, event: WorkflowEvent) -> None:
        self._history.append(event)
        for handler in self._subscribers:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
