from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from domaintoolbelt.core.prompt_loader import PromptLoader
from domaintoolbelt.core.types import (
    DomainConfig,
    FidelityPolicy,
    ToolSpec,
    ValidationResult,
)


class TemplatePack:
    """Copy this class into a new pack and replace the placeholder values."""

    def __init__(self, storage_root: str | Path = ".domaintoolbelt") -> None:
        prompt_dir = Path(__file__).parent / "prompts"
        self._prompt_loader = PromptLoader(prompt_dir)
        self.config = DomainConfig(
            key="template_pack",
            display_name="Template Pack",
            description="Starter template for new community packs.",
            system_prompt_dir=prompt_dir,
            fidelity=FidelityPolicy(),
            tools=(
                ToolSpec(
                    name="lookup_primary_source",
                    description="Retrieve the strongest primary sources for the query.",
                    input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                    authoritative=True,
                    source_scope="primary",
                    tags=("primary",),
                ),
            ),
        )

    async def run_tool(
        self,
        tool_name: str,
        instruction: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Any:
        raise NotImplementedError("Replace the template tool implementations before use.")

    async def retrieve_context(self, query: str, top_k: int = 5) -> list[str]:
        return []

    def validate_step(self, tool_name: str, output: Any) -> ValidationResult:
        return ValidationResult(ok=True)

    def fidelity_audit(self, synthesis: str, citations: tuple[str, ...]) -> ValidationResult:
        return ValidationResult(ok=True)

    def load_prompt(self, filename: str, **variables: Any) -> str:
        return self._prompt_loader.load(filename, **variables)
