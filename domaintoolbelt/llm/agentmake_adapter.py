from __future__ import annotations

from typing import Any, Callable

from domaintoolbelt.llm.provider import LLMProvider, ProviderConfig


class AgentMakeAdapter(LLMProvider):
    def __init__(self, agentmake: Callable[..., Any]) -> None:
        self.agentmake = agentmake

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        config: ProviderConfig | None = None,
    ) -> str:
        response = self.agentmake(
            prompt,
            system=system,
            model=(config.model if config else "") or None,
            temperature=(config.temperature if config else None),
            max_tokens=(config.max_tokens if config else None),
        )
        return str(response)
