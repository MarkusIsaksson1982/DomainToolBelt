from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import math
from pathlib import Path


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


@dataclass
class MemoryEntry:
    session_id: str
    request: str
    answer: str
    citations: tuple[str, ...]
    created_at: str


class MemoryStore:
    def __init__(
        self,
        root: str | Path = ".domaintoolbelt/memory",
        decay_half_life_days: float = 30.0,
    ):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "memory.jsonl"
        self.decay_half_life_days = decay_half_life_days

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        entries = self._load_entries()
        query_tokens = _tokenize(query)
        scored: list[tuple[float, MemoryEntry]] = []
        for entry in entries:
            haystack = f"{entry.request} {entry.answer}"
            score = float(len(query_tokens & _tokenize(haystack)))
            if score > 0 and self.decay_half_life_days > 0:
                created_at = datetime.fromisoformat(entry.created_at)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_days = max(
                    0.0,
                    (datetime.now(timezone.utc) - created_at).total_seconds() / 86400.0,
                )
                score *= math.pow(2.0, -age_days / self.decay_half_life_days)
            scored.append((score, entry))

        scored.sort(key=lambda item: (-item[0], item[1].created_at))
        matches = [entry.answer for score, entry in scored if score > 0]
        return matches[:top_k]

    async def append(
        self,
        session_id: str,
        request: str,
        answer: str,
        citations: tuple[str, ...],
    ) -> None:
        entry = MemoryEntry(
            session_id=session_id,
            request=request,
            answer=answer,
            citations=citations,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(entry)) + "\n")

    def _load_entries(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        entries: list[MemoryEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            entries.append(
                MemoryEntry(
                    session_id=payload["session_id"],
                    request=payload["request"],
                    answer=payload["answer"],
                    citations=tuple(payload.get("citations", ())),
                    created_at=payload["created_at"],
                )
            )
        return entries
