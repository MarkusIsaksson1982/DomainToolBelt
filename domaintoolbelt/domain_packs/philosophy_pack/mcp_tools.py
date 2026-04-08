from __future__ import annotations

import re
from typing import Any, Mapping

from domaintoolbelt.core.types import ToolResult
from domaintoolbelt.rag.retriever import KeywordRetriever


_REFERENCE_RE = re.compile(
    r"\b(?:Plato, Republic \d+[a-z]|Aristotle, NE \d+[a-z]|Descartes, Meditations II|Kant, CPR A\d+/B\d+|Hume, Enquiry 4\.1)\b"
)

_CORPUS = [
    {
        "id": "Plato, Republic 514a",
        "text": "Imagine human beings living in an underground den, which has a mouth open towards the light.",
    },
    {
        "id": "Plato, Republic 515a",
        "text": "At first, when any of them is liberated and compelled suddenly to stand up and turn his neck round, he will suffer sharp pains.",
    },
    {
        "id": "Aristotle, NE 1094a",
        "text": "Every art and every inquiry, and similarly every action and pursuit, is thought to aim at some good.",
    },
    {
        "id": "Descartes, Meditations II",
        "text": "I am, I exist, is necessarily true each time that I pronounce it, or that I mentally conceive it.",
    },
    {
        "id": "Kant, CPR A51/B75",
        "text": "Thoughts without content are empty, intuitions without concepts are blind.",
    },
    {
        "id": "Hume, Enquiry 4.1",
        "text": "All the objects of human reason or enquiry may naturally be divided into two kinds, namely Relations of Ideas, and Matters of Fact.",
    },
]

_CROSS_REFERENCES = {
    "Plato, Republic 514a": ("Plato, Republic 515a", "Kant, CPR A51/B75"),
    "Descartes, Meditations II": ("Hume, Enquiry 4.1", "Kant, CPR A51/B75"),
    "Aristotle, NE 1094a": ("Plato, Republic 514a",),
    "Hume, Enquiry 4.1": ("Descartes, Meditations II", "Kant, CPR A51/B75"),
}


def build_retriever() -> KeywordRetriever:
    return KeywordRetriever(corpus_records())


def corpus_records() -> list[dict[str, str]]:
    return [{"id": item["id"], "text": f"[{item['id']}] {item['text']}"} for item in _CORPUS]


async def lookup_argument(instruction: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
    query = _extract_query(instruction, arguments)
    matches = build_retriever().search(query, top_k=4)
    citations = tuple(item["id"] for item in matches)
    passages = [item["text"] for item in matches]
    summary = "Primary philosophical passages: " + "; ".join(passages)
    return ToolResult(
        content={"summary": summary, "citations": citations, "passages": passages},
        citations=citations,
    )


async def cross_tradition_reference(
    instruction: str,
    arguments: Mapping[str, Any] | None = None,
) -> ToolResult:
    seed_text = _extract_query(instruction, arguments)
    seed_citations = _extract_references(seed_text)
    related: list[str] = []
    for citation in seed_citations:
        related.extend(_CROSS_REFERENCES.get(citation, ()))

    if not related:
        if "knowledge" in seed_text.lower() or "epistem" in seed_text.lower():
            related = ["Descartes, Meditations II", "Hume, Enquiry 4.1", "Kant, CPR A51/B75"]
        else:
            related = ["Plato, Republic 514a", "Aristotle, NE 1094a"]

    rendered = [f"[{reference}] {_lookup_text(reference)}" for reference in related]
    citations = tuple(related)
    summary = "Cross-tradition references: " + "; ".join(rendered)
    return ToolResult(
        content={"summary": summary, "citations": citations, "passages": rendered},
        citations=citations,
    )


async def dialectical_summary(
    instruction: str,
    arguments: Mapping[str, Any] | None = None,
) -> ToolResult:
    arguments = arguments or {}
    primary = str(arguments.get("primary") or instruction)
    secondary = str(arguments.get("secondary") or "")
    combined = f"{instruction}\n{primary}\n{secondary}"
    references = _extract_references(combined)
    if not references:
        references = ("Descartes, Meditations II", "Hume, Enquiry 4.1", "Kant, CPR A51/B75")

    if "knowledge" in combined.lower() or "epistem" in combined.lower():
        summary = (
            "Descartes treats 'I am, I exist' as a point of certainty [Descartes, Meditations II], "
            "Hume divides inquiry into relations of ideas and matters of fact [Hume, Enquiry 4.1], "
            "and Kant says thoughts without content are empty while intuitions without concepts are blind "
            "[Kant, CPR A51/B75]."
        )
        citations = (
            "Descartes, Meditations II",
            "Hume, Enquiry 4.1",
            "Kant, CPR A51/B75",
        )
    else:
        citations = references
        summary = (
            "The gathered passages present a coherent philosophical theme "
            + "".join(f"[{citation}]" for citation in citations)
            + "."
        )

    return ToolResult(
        content={"summary": summary, "citations": citations, "theme": "philosophy"},
        citations=tuple(citations),
    )


TOOLS = {
    "lookup_argument": lookup_argument,
    "cross_tradition_reference": cross_tradition_reference,
    "dialectical_summary": dialectical_summary,
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
    return "Reference text placeholder."
