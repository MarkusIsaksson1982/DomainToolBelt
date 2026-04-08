from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

from domaintoolbelt.core.types import DomainConfig, ValidationResult


@runtime_checkable
class DomainPack(Protocol):
    config: DomainConfig

    async def run_tool(
        self,
        tool_name: str,
        instruction: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> Any: ...

    async def retrieve_context(self, query: str, top_k: int = 5) -> list[str]: ...

    def validate_step(self, tool_name: str, output: Any) -> ValidationResult: ...

    def fidelity_audit(self, synthesis: str, citations: tuple[str, ...]) -> ValidationResult: ...

    def load_prompt(self, filename: str, **variables: Any) -> str: ...


def has_prompts(pack: Any) -> bool:
    return callable(getattr(pack, "load_prompt", None))
