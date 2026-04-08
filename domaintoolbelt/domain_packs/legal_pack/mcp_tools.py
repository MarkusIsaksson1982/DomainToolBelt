from __future__ import annotations

import re
from typing import Any, Mapping

from domaintoolbelt.core.types import ToolResult
from domaintoolbelt.rag.retriever import KeywordRetriever


_REFERENCE_RE = re.compile(r"\bGDPR (?:Art\.|Recital) \d+\b")

_CORPUS = [
    {
        "id": "GDPR Art. 5",
        "text": "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject.",
    },
    {
        "id": "GDPR Art. 6",
        "text": "Processing shall be lawful only if and to the extent that at least one of the lawful bases applies.",
    },
    {
        "id": "GDPR Art. 12",
        "text": "The controller shall take appropriate measures to provide information in a concise, transparent, intelligible and easily accessible form.",
    },
    {
        "id": "GDPR Art. 13",
        "text": "Where personal data relating to a data subject are collected from the data subject, the controller shall provide the identity of the controller and the purposes of the processing.",
    },
    {
        "id": "GDPR Art. 15",
        "text": "The data subject shall have the right to obtain confirmation as to whether or not personal data concerning them are being processed, and access to that personal data.",
    },
    {
        "id": "GDPR Recital 39",
        "text": "Any processing of personal data should be lawful and fair. Natural persons should be made aware of risks, rules, safeguards and rights in relation to the processing of personal data.",
    },
]

_CROSS_REFERENCES = {
    "GDPR Art. 5": ("GDPR Art. 12", "GDPR Recital 39"),
    "GDPR Art. 6": ("GDPR Art. 13",),
    "GDPR Art. 12": ("GDPR Art. 13", "GDPR Recital 39"),
    "GDPR Art. 13": ("GDPR Art. 12", "GDPR Art. 15"),
    "GDPR Art. 15": ("GDPR Art. 12",),
}


def build_retriever() -> KeywordRetriever:
    return KeywordRetriever(corpus_records())


def corpus_records() -> list[dict[str, str]]:
    return [{"id": item["id"], "text": f"[{item['id']}] {item['text']}"} for item in _CORPUS]


async def lookup_statute(instruction: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
    query = _extract_query(instruction, arguments)
    matches = build_retriever().search(query, top_k=4)
    citations = tuple(item["id"] for item in matches)
    passages = [item["text"] for item in matches]
    summary = "Primary legal authorities: " + "; ".join(passages)
    return ToolResult(
        content={"summary": summary, "citations": citations, "passages": passages},
        citations=citations,
    )


async def cross_reference_authority(
    instruction: str,
    arguments: Mapping[str, Any] | None = None,
) -> ToolResult:
    seed_text = _extract_query(instruction, arguments)
    seed_citations = _extract_references(seed_text)
    related: list[str] = []
    for citation in seed_citations:
        related.extend(_CROSS_REFERENCES.get(citation, ()))

    if not related:
        if "access" in seed_text.lower():
            related = ["GDPR Art. 12", "GDPR Art. 15"]
        else:
            related = ["GDPR Art. 5", "GDPR Recital 39"]

    rendered = [f"[{reference}] {_lookup_text(reference)}" for reference in related]
    summary = "Cross references: " + "; ".join(rendered)
    citations = tuple(related)
    return ToolResult(
        content={"summary": summary, "citations": citations, "passages": rendered},
        citations=citations,
    )


async def legal_summary(instruction: str, arguments: Mapping[str, Any] | None = None) -> ToolResult:
    arguments = arguments or {}
    primary = str(arguments.get("primary") or instruction)
    secondary = str(arguments.get("secondary") or "")
    combined = f"{instruction}\n{primary}\n{secondary}"
    references = _extract_references(combined)
    if not references:
        references = ("GDPR Art. 5", "GDPR Art. 12")

    if "access" in combined.lower():
        summary = (
            "The cited GDPR materials frame access rights as part of transparent processing. "
            "Controllers must provide intelligible information and enable access to personal data "
            "[GDPR Art. 12][GDPR Art. 15]. Those duties sit within the broader principles of lawful, "
            "fair, and transparent processing [GDPR Art. 5][GDPR Recital 39]."
        )
        citations = ("GDPR Art. 12", "GDPR Art. 15", "GDPR Art. 5", "GDPR Recital 39")
    else:
        citations = references
        summary = (
            "The gathered authorities consistently support the requested legal theme "
            + "".join(f"[{citation}]" for citation in citations)
            + "."
        )

    return ToolResult(
        content={"summary": summary, "citations": citations, "theme": "gdpr"},
        citations=tuple(citations),
    )


TOOLS = {
    "lookup_statute": lookup_statute,
    "cross_reference_authority": cross_reference_authority,
    "legal_summary": legal_summary,
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
