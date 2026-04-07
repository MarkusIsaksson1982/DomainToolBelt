from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Iterable, Protocol

from domaintoolbelt.core.types import ToolSpec


_LIST_RE = re.compile(r"\[[\s\S]*\]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def safe_parse_tool_list(raw: str, allowed: set[str]) -> list[str]:
    match = _LIST_RE.search(raw or "")
    if not match:
        return []
    try:
        parsed = ast.literal_eval(match.group(0))
    except (SyntaxError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [name for name in parsed if isinstance(name, str) and name in allowed]


class ToolReranker(Protocol):
    async def rerank(self, suggestion: str, candidate_tools: list[str]) -> str: ...


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


@dataclass
class VectorToolSelector:
    tools: Iterable[ToolSpec]
    embedding_model: str = "lexical-overlap"
    reranker: ToolReranker | None = None
    _tool_list: list[ToolSpec] = field(init=False, repr=False)
    _tool_docs: dict[str, set[str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._tool_list = list(self.tools)
        self._tool_docs = {
            tool.name: _tokenize(" ".join((tool.name, tool.description, " ".join(tool.tags))))
            for tool in self._tool_list
        }

    async def select(
        self,
        suggestion: str,
        top_k: int = 12,
        preferred: tuple[str, ...] = (),
    ) -> list[str]:
        allowed = {tool.name for tool in self._tool_list}
        ranked_candidates = self._rank_candidates(suggestion, top_k=top_k)
        ranked_names = [name for name, _score in ranked_candidates]

        for tool_name in reversed(preferred):
            if tool_name in ranked_names:
                ranked_names.remove(tool_name)
                ranked_names.insert(0, tool_name)

        if self.reranker:
            raw = await self.reranker.rerank(suggestion, ranked_names)
            parsed = safe_parse_tool_list(raw, allowed)
            if parsed:
                return parsed

        return ranked_names[:top_k]

    def _rank_candidates(self, suggestion: str, top_k: int) -> list[tuple[str, float]]:
        query_tokens = _tokenize(suggestion)
        scored: list[tuple[str, float]] = []
        for tool in self._tool_list:
            doc_tokens = self._tool_docs[tool.name]
            overlap = len(query_tokens & doc_tokens)
            scope_bonus = 0.1 if tool.source_scope == "primary" else 0.0
            authority_bonus = 0.2 if tool.authoritative else 0.0
            score = overlap + scope_bonus + authority_bonus
            scored.append((tool.name, score))

        scored.sort(key=lambda item: (-item[1], item[0]))
        return scored[:top_k]
