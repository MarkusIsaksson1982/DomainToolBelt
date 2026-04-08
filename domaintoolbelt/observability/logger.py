from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
from pathlib import Path
from typing import Any

from domaintoolbelt.core.events import EventBus, WorkflowCompletedEvent, WorkflowEvent


class TraceLogger:
    def __init__(self, trace_dir: str | Path = ".domaintoolbelt/traces") -> None:
        self.trace_dir = Path(trace_dir)
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, Path] = {}

    def attach(self, event_bus: EventBus) -> None:
        event_bus.subscribe(self._on_event)

    async def _on_event(self, event: WorkflowEvent) -> None:
        path = self._get_file(event.session_id)
        record = {
            "timestamp": event.created_at,
            "event_type": event.event_type,
            "session_id": event.session_id,
            "payload": self._serialize_event(event),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

        if isinstance(event, WorkflowCompletedEvent):
            final_path = self.trace_dir / f"{event.session_id}.final.txt"
            final_path.write_text(event.final_answer, encoding="utf-8")

    def _get_file(self, session_id: str) -> Path:
        if session_id not in self._files:
            self._files[session_id] = self.trace_dir / f"{session_id}.jsonl"
        return self._files[session_id]

    def _serialize_event(self, event: WorkflowEvent) -> dict[str, Any]:
        payload = asdict(event) if is_dataclass(event) else dict(event.__dict__)
        return {key: self._coerce(value) for key, value in payload.items()}

    def _coerce(self, value: Any) -> Any:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, dict):
            return {key: self._coerce(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._coerce(item) for item in value]
        return value
