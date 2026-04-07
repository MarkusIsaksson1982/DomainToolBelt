from __future__ import annotations

import re
from collections.abc import Sequence


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class KeywordRetriever:
    def __init__(self, records: Sequence[dict[str, str]]):
        self.records = list(records)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, str]]:
        query_tokens = _tokenize(query)
        ranked: list[tuple[float, dict[str, str]]] = []
        for record in self.records:
            record_tokens = _tokenize(record["text"])
            overlap = len(query_tokens & record_tokens)
            citation_bonus = 0.5 if record["id"].lower() in query.lower() else 0.0
            ranked.append((overlap + citation_bonus, record))

        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        matches = [record for score, record in ranked if score > 0]
        if matches:
            return matches[:top_k]
        return [record for _score, record in ranked[:top_k]]
