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
from domaintoolbelt.domain_packs.legal_pack.mcp_tools import TOOLS, build_retriever, corpus_records
from domaintoolbelt.domain_packs.legal_pack.truth_policy import LEGAL_FIDELITY_POLICY
from domaintoolbelt.domain_packs.legal_pack.validators import validate_legal_output
from domaintoolbelt.rag.retriever import KeywordRetriever


class LegalPack:
    def __init__(self, storage_root: str | Path = ".domaintoolbelt") -> None:
        root = Path(storage_root)
        prompt_dir = Path(__file__).parent / "prompts"
        self._prompt_loader = PromptLoader(prompt_dir)
        self._retriever: KeywordRetriever = build_retriever()

        self.config = DomainConfig(
            key="legal_pack",
            display_name="Legal Reference Pack",
            description="Reference legal pack grounded in sample GDPR materials.",
            system_prompt_dir=prompt_dir,
            fidelity=LEGAL_FIDELITY_POLICY,
            tools=(
                ToolSpec(
                    name="lookup_statute",
                    description="Retrieve the strongest primary legal authorities for a query.",
                    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                    authoritative=True,
                    source_scope="statute",
                    tags=("primary", "statute", "verbatim"),
                ),
                ToolSpec(
                    name="cross_reference_authority",
                    description="Find supporting legal authorities that reinforce the primary authorities.",
                    input_schema={"type": "object", "properties": {"seed_summary": {"type": "string"}}},
                    source_scope="regulation",
                    tags=("cross", "reference", "secondary"),
                ),
                ToolSpec(
                    name="legal_summary",
                    description="Compose a grounded legal summary from the gathered authorities.",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "primary": {"type": "string"},
                            "secondary": {"type": "string"},
                        },
                    },
                    source_scope="statute",
                    tags=("summary", "synthesis"),
                ),
            ),
            tool_registry=ToolRegistryConfig(max_tools_per_step=3),
            rag=RAGConfig(
                enabled=True,
                corpus_path=root / "legal_corpus",
                top_k_retrieval=4,
                similarity_threshold=0.2,
                verbatim_sources=tuple(record["id"] for record in corpus_records()),
            ),
            memory=MemoryConfig(store_path=root / "memory"),
            validation=ValidationConfig(max_retries=1),
            guardrails=GuardrailConfig(
                tradition_flags={
                    "jurisdiction": "EU",
                    "instrument": "GDPR sample corpus",
                    "fidelity": "citation required",
                },
                require_corpus_citation=True,
                require_primary_source=True,
            ),
            max_parallel_steps=2,
            tradition_flags={"domain": "legal", "scope": "reference"},
        )

    async def run_tool(
        self,
        tool_name: str,
        instruction: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Any:
        if tool_name not in TOOLS:
            raise KeyError(f"Unknown legal pack tool: {tool_name}")
        return await TOOLS[tool_name](instruction, arguments)

    async def retrieve_context(self, query: str, top_k: int = 5) -> list[str]:
        matches = self._retriever.search(query, top_k=top_k)
        return [item["text"] for item in matches]

    def validate_step(self, tool_name: str, output: Any) -> ValidationResult:
        return validate_legal_output(tool_name, output)

    def fidelity_audit(self, synthesis: str, citations: tuple[str, ...]) -> ValidationResult:
        issues: list[str] = []
        if not citations:
            issues.append("Final synthesis must include explicit legal citations.")
        if "I think" in synthesis or "probably" in synthesis.lower():
            issues.append("Final synthesis contains speculative language.")
        return ValidationResult(ok=not issues, issues=tuple(issues))

    def disambiguate_intent(self, query: str) -> str:
        lowered = query.lower()
        if "access" in lowered:
            return "The request concerns data subject access and transparency."
        if "lawful" in lowered or "lawfulness" in lowered:
            return "The request concerns lawful bases and processing principles."
        return "The request concerns legal interpretation."

    def load_prompt(self, filename: str, **variables: Any) -> str:
        return self._prompt_loader.load(filename, **variables)
