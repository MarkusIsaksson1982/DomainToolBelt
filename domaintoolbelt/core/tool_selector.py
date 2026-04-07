from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from domaintoolbelt.core.types import ToolSpec

try:
    from agentmake.utils.rag import cosine_similarity_matrix, get_embeddings
except ImportError:
    cosine_similarity_matrix = None
    get_embeddings = None


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
    _tool_names: list[str] = field(init=False, repr=False)
    _tool_vectors: Any = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        self._tool_list = list(self.tools)
        self._tool_names = [tool.name for tool in self._tool_list]
        self._tool_docs = {
            tool.name: _tokenize(" ".join((tool.name, tool.description, " ".join(tool.tags))))
            for tool in self._tool_list
        }
        if get_embeddings:
            docs = [
                "\n".join(filter(None, (tool.name, tool.description, " ".join(tool.tags))))
                for tool in self._tool_list
            ]
            try:
                self._tool_vectors = get_embeddings(docs, model=self.embedding_model)
            except Exception:
                self._tool_vectors = None

    async def select(
        self,
        suggestion: str,
        top_k: int = 12,
        preferred: tuple[str, ...] = (),
    ) -> list[str]:
        allowed = {tool.name for tool in self._tool_list}
        ranked_candidates = self._embedding_rank_candidates(suggestion, top_k=top_k)
        if not ranked_candidates:
            ranked_candidates = self._lexical_rank_candidates(suggestion, top_k=top_k)
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

    def _lexical_rank_candidates(self, suggestion: str, top_k: int) -> list[tuple[str, float]]:
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

    def _embedding_rank_candidates(self, suggestion: str, top_k: int) -> list[tuple[str, float]]:
        if not (get_embeddings and cosine_similarity_matrix and self._tool_vectors is not None):
            return []

        try:
            query_vectors = get_embeddings([suggestion], model=self.embedding_model)
            if not query_vectors:
                return []
            scores = cosine_similarity_matrix(query_vectors[0], self._tool_vectors)
        except Exception:
            return []

        flattened = self._flatten_scores(scores)
        if not flattened:
            return []

        order = sorted(range(len(flattened)), key=lambda index: flattened[index], reverse=True)
        return [
            (self._tool_names[index], float(flattened[index]))
            for index in order[:top_k]
        ]

    @staticmethod
    def _flatten_scores(scores: Any) -> list[float]:
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        if isinstance(scores, (tuple, list)) and scores and isinstance(scores[0], (tuple, list)):
            scores = scores[0]
        if not isinstance(scores, (tuple, list)):
            return []
        flattened: list[float] = []
        for value in scores:
            try:
                flattened.append(float(value))
            except (TypeError, ValueError):
                return []
        return flattened
