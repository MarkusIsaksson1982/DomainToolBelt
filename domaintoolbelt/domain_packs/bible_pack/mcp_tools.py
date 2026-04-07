from __future__ import annotations

import re
from typing import Any, Mapping

from domaintoolbelt.rag.retriever import KeywordRetriever


_REFERENCE_RE = re.compile(r"\b(?:[1-3]\s*)?[A-Za-z]+\s+\d+:\d+\b")

_CORPUS = [
    {
        "id": "Romans 8:14",
        "text": "For as many as are led by the Spirit of God, they are the sons of God.",
    },
    {
        "id": "Romans 8:15",
        "text": "For ye have not received the spirit of bondage again to fear; but ye have received the Spirit of adoption, whereby we cry, Abba, Father.",
    },
    {
        "id": "Romans 8:16",
        "text": "The Spirit itself beareth witness with our spirit, that we are the children of God:",
    },
    {
        "id": "Romans 8:17",
        "text": "And if children, then heirs; heirs of God, and joint-heirs with Christ.",
    },
    {
        "id": "Galatians 4:6",
        "text": "And because ye are sons, God hath sent forth the Spirit of his Son into your hearts, crying, Abba, Father.",
    },
    {
        "id": "Ephesians 1:5",
        "text": "Having predestinated us unto the adoption of children by Jesus Christ to himself.",
    },
    {
        "id": "John 1:12",
        "text": "But as many as received him, to them gave he power to become the sons of God.",
    },
]

_CROSS_REFERENCES = {
    "Romans 8:15": ("Galatians 4:6", "Ephesians 1:5"),
    "Romans 8:16": ("John 1:12",),
    "Romans 8:17": ("Galatians 4:7", "Ephesians 1:5"),
}

_EXTRA_REFERENCES = {
    "Galatians 4:7": "Wherefore thou art no more a servant, but a son; and if a son, then an heir of God through Christ.",
}


def build_retriever() -> KeywordRetriever:
    records = [{"id": item["id"], "text": f"[{item['id']}] {item['text']}"} for item in _CORPUS]
    records.extend(
        {"id": key, "text": f"[{key}] {value}"} for key, value in _EXTRA_REFERENCES.items()
    )
    return KeywordRetriever(records)


def corpus_records() -> list[dict[str, str]]:
    records = [{"id": item["id"], "text": f"[{item['id']}] {item['text']}"} for item in _CORPUS]
    records.extend(
        {"id": key, "text": f"[{key}] {value}"} for key, value in _EXTRA_REFERENCES.items()
    )
    return records


async def lookup_passage(instruction: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    query = _extract_query(instruction, arguments)
    matches = build_retriever().search(query, top_k=4)
    citations = [item["id"] for item in matches]
    passages = [item["text"] for item in matches]
    summary = "Primary passages: " + "; ".join(passages)
    return {"summary": summary, "citations": citations, "passages": passages}


async def cross_reference(instruction: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    seed_text = _extract_query(instruction, arguments)
    seed_citations = _extract_references(seed_text)
    related: list[str] = []
    for citation in seed_citations:
        related.extend(_CROSS_REFERENCES.get(citation, ()))

    if not related:
        if "adoption" in seed_text.lower():
            related = ["Galatians 4:6", "Ephesians 1:5", "John 1:12"]
        else:
            related = ["John 1:12", "Galatians 4:6"]

    rendered = [f"[{reference}] {_lookup_text(reference)}" for reference in related]
    summary = "Cross references: " + "; ".join(rendered)
    return {"summary": summary, "citations": related, "passages": rendered}


async def theme_summary(instruction: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    arguments = arguments or {}
    primary = str(arguments.get("primary") or instruction)
    secondary = str(arguments.get("secondary") or "")
    combined = f"{instruction}\n{primary}\n{secondary}"
    references = _extract_references(combined)
    if not references:
        references = ("Romans 8:15", "Romans 8:16", "Romans 8:17")

    if "adoption" in combined.lower():
        summary = (
            "Romans 8 presents adoption as Spirit-enabled sonship: believers receive the Spirit "
            "of adoption, are identified as God's children, and are named heirs with Christ "
            "[Romans 8:15][Romans 8:16][Romans 8:17]. Related texts connect that sonship to "
            "God's prior purpose and the cry of 'Abba, Father' [Galatians 4:6][Ephesians 1:5]."
        )
        citations = ["Romans 8:15", "Romans 8:16", "Romans 8:17", "Galatians 4:6", "Ephesians 1:5"]
    else:
        citations = list(references)
        summary = (
            "The gathered passages point to a coherent biblical theme grounded in the cited texts "
            + "".join(f"[{citation}]" for citation in citations)
            + "."
        )

    return {"summary": summary, "citations": citations, "theme": "adoption" if "adoption" in combined.lower() else "general"}


TOOLS = {
    "lookup_passage": lookup_passage,
    "cross_reference": cross_reference,
    "theme_summary": theme_summary,
}


def _extract_query(instruction: str, arguments: Mapping[str, Any] | None) -> str:
    if arguments:
        for key in ("query", "seed_summary", "primary", "secondary"):
            if arguments.get(key):
                return str(arguments[key])
    return instruction


def _extract_references(text: str) -> tuple[str, ...]:
    seen: list[str] = []
    bracketed = re.findall(r"\[([^\[\]]+)\]", text)
    raw = bracketed + _REFERENCE_RE.findall(text)
    for reference in raw:
        cleaned = reference.strip()
        if cleaned not in seen:
            seen.append(cleaned)
    return tuple(seen)


def _lookup_text(reference: str) -> str:
    for record in _CORPUS:
        if record["id"] == reference:
            return record["text"]
    return _EXTRA_REFERENCES.get(reference, "Reference text placeholder.")
