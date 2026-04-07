from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


_CITATION_RE = re.compile(r"\[([^\[\]]+)\]")


def extract_citations(value: Any) -> tuple[str, ...]:
    citations: list[str] = []
    for text in _iter_text(value):
        for citation in _CITATION_RE.findall(text):
            if citation not in citations:
                citations.append(citation)
    return tuple(citations)


def _iter_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        texts: list[str] = []
        for item in value.values():
            texts.extend(_iter_text(item))
        return texts
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        texts: list[str] = []
        for item in value:
            texts.extend(_iter_text(item))
        return texts
    return [str(value)]
