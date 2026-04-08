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
from domaintoolbelt.domain_packs.philosophy_pack.mcp_tools import TOOLS, build_retriever, corpus_records
from domaintoolbelt.domain_packs.philosophy_pack.truth_policy import PHILOSOPHY_FIDELITY_POLICY
from domaintoolbelt.domain_packs.philosophy_pack.validators import validate_philosophy_output
from domaintoolbelt.rag.retriever import KeywordRetriever


class PhilosophyPack:
    def __init__(self, storage_root: str | Path = ".domaintoolbelt") -> None:
        root = Path(storage_root)
        prompt_dir = Path(__file__).parent / "prompts"
        self._prompt_loader = PromptLoader(prompt_dir)
        self._retriever: KeywordRetriever = build_retriever()

        self.config = DomainConfig(
            key="philosophy_pack",
            display_name="Philosophy Reference Pack",
            description="Reference philosophy pack grounded in a small public-domain corpus.",
            system_prompt_dir=prompt_dir,
            fidelity=PHILOSOPHY_FIDELITY_POLICY,
            tools=(
                ToolSpec(
                    name="lookup_argument",
                    description="Retrieve the strongest primary philosophical passages for a query.",
                    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                    authoritative=True,
                    source_scope="primary",
                    tags=("primary", "argument", "reference"),
                ),
                ToolSpec(
                    name="cross_tradition_reference",
                    description="Find supporting or contrasting passages across philosophical traditions.",
                    input_schema={"type": "object", "properties": {"seed_summary": {"type": "string"}}},
                    source_scope="commentary",
                    tags=("cross", "reference", "secondary", "tradition"),
                ),
                ToolSpec(
                    name="dialectical_summary",
                    description="Compose a grounded synthesis that preserves the philosophical tensions in the evidence.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "primary": {"type": "string"},
                            "secondary": {"type": "string"},
                        },
                    },
                    source_scope="primary",
                    tags=("summary", "synthesis", "dialectic"),
                ),
            ),
            tool_registry=ToolRegistryConfig(max_tools_per_step=3),
            rag=RAGConfig(
                enabled=True,
                corpus_path=root / "philosophy_corpus",
                top_k_retrieval=4,
                similarity_threshold=0.2,
                verbatim_sources=tuple(record["id"] for record in corpus_records()),
            ),
            memory=MemoryConfig(store_path=root / "memory"),
            validation=ValidationConfig(max_retries=1),
            guardrails=GuardrailConfig(
                tradition_flags={
                    "method": "primary-source-first",
                    "schools": "ancient,early_modern,empiricist,critical",
                    "fidelity": "citation required",
                },
                require_corpus_citation=True,
                require_primary_source=True,
            ),
            max_parallel_steps=2,
            tradition_flags={"domain": "philosophy", "mode": "reference"},
        )

    async def run_tool(
        self,
        tool_name: str,
        instruction: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Any:
        if tool_name not in TOOLS:
            raise KeyError(f"Unknown philosophy pack tool: {tool_name}")
        return await TOOLS[tool_name](instruction, arguments)

    async def retrieve_context(self, query: str, top_k: int = 5) -> list[str]:
        matches = self._retriever.search(query, top_k=top_k)
        return [item["text"] for item in matches]

    def validate_step(self, tool_name: str, output: Any) -> ValidationResult:
        return validate_philosophy_output(tool_name, output)

    def fidelity_audit(self, synthesis: str, citations: tuple[str, ...]) -> ValidationResult:
        issues: list[str] = []
        if not citations:
            issues.append("Final synthesis must include explicit philosophy citations.")
        if "obviously" in synthesis.lower() or "clearly" in synthesis.lower():
            issues.append("Final synthesis contains overconfident philosophical language.")
        return ValidationResult(ok=not issues, issues=tuple(issues))

    def disambiguate_intent(self, query: str) -> str:
        lowered = query.lower()
        if any(term in lowered for term in ("knowledge", "epistem", "justify")):
            return "The request concerns epistemology."
        if any(term in lowered for term in ("good", "virtue", "ethic", "moral")):
            return "The request concerns ethics."
        if any(term in lowered for term in ("exist", "being", "reality", "metaphys")):
            return "The request concerns metaphysics."
        return "The request concerns philosophical interpretation."

    def load_prompt(self, filename: str, **variables: Any) -> str:
        return self._prompt_loader.load(filename, **variables)
