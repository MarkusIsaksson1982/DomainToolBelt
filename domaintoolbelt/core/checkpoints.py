from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


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
