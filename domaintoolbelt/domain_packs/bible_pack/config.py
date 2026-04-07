from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from domaintoolbelt.core.prompt_loader import PromptLoader
from domaintoolbelt.core.types import (
    DomainConfig,
    GuardrailConfig,
    MemoryConfig,
    RAGConfig,
    ToolRegistryConfig,
    ToolSpec,
    ValidationConfig,
    ValidationResult,
)
from domaintoolbelt.domain_packs.bible_pack.mcp_tools import TOOLS, build_retriever, corpus_records
from domaintoolbelt.domain_packs.bible_pack.truth_policy import BIBLE_FIDELITY_POLICY
from domaintoolbelt.domain_packs.bible_pack.validators import validate_bible_output
from domaintoolbelt.rag.retriever import KeywordRetriever


class BiblePack:
    def __init__(self, storage_root: str | Path = ".domaintoolbelt") -> None:
        root = Path(storage_root)
        prompt_dir = Path(__file__).parent / "prompts"
        self._prompt_loader = PromptLoader(prompt_dir)
        self._retriever: KeywordRetriever = build_retriever()

        self.config = DomainConfig(
            key="bible_pack",
            display_name="Bible Reference Pack",
            description="Reference Bible pack for the DomainToolBelt starter repository.",
            system_prompt_dir=prompt_dir,
            fidelity=BIBLE_FIDELITY_POLICY,
            tools=(
                ToolSpec(
                    name="lookup_passage",
                    description="Retrieve the strongest primary biblical passages for a query.",
                    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                    authoritative=True,
                    source_scope="primary",
                    tags=("passage", "reference", "primary"),
                ),
                ToolSpec(
                    name="cross_reference",
                    description="Find supporting cross references connected to the primary passages.",
                    input_schema={"type": "object", "properties": {"seed_summary": {"type": "string"}}},
                    source_scope="cross_reference",
                    tags=("cross", "reference", "related"),
                ),
                ToolSpec(
                    name="theme_summary",
                    description="Compose a grounded synthesis from the gathered passages.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "primary": {"type": "string"},
                            "secondary": {"type": "string"},
                        },
                    },
                    source_scope="primary",
                    tags=("summary", "theme", "synthesis"),
                ),
            ),
            tool_registry=ToolRegistryConfig(max_tools_per_step=3),
            rag=RAGConfig(
                enabled=True,
                corpus_path=root / "corpus",
                top_k_retrieval=4,
                verbatim_sources=tuple(record["id"] for record in corpus_records()),
            ),
            memory=MemoryConfig(store_path=root / "memory"),
            validation=ValidationConfig(max_retries=1),
            guardrails=GuardrailConfig(
                tradition_flags={
                    "translation": "KJV sample corpus",
                    "method": "reference pack",
                    "fidelity": "citation required",
                },
                require_corpus_citation=True,
                require_primary_source=True,
            ),
            max_parallel_steps=2,
            tradition_flags={"domain": "bible", "mode": "reference"},
        )

    async def run_tool(
        self,
        tool_name: str,
        instruction: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Any:
        if tool_name not in TOOLS:
            raise KeyError(f"Unknown Bible pack tool: {tool_name}")
        return await TOOLS[tool_name](instruction, arguments)

    async def retrieve_context(self, query: str, top_k: int = 5) -> list[str]:
        matches = self._retriever.search(query, top_k=top_k)
        return [item["text"] for item in matches]

    def validate_step(self, tool_name: str, output: Any) -> ValidationResult:
        return validate_bible_output(tool_name, output)

    def fidelity_audit(self, synthesis: str, citations: tuple[str, ...]) -> ValidationResult:
        issues: list[str] = []
        if not citations:
            issues.append("Final synthesis must include explicit citations.")
        if "I think" in synthesis:
            issues.append("Final synthesis contains speculative language.")
        return ValidationResult(ok=not issues, issues=tuple(issues))

    def disambiguate_intent(self, query: str) -> str:
        lowered = query.lower()
        if "adoption" in lowered:
            return "The request concerns adoption/sonship language."
        if "heir" in lowered or "inherit" in lowered:
            return "The request concerns inheritance language."
        return "The request concerns biblical interpretation."

    def load_prompt(self, filename: str, **variables: Any) -> str:
        return self._prompt_loader.load(filename, **variables)
