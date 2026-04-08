from __future__ import annotations

from domaintoolbelt.llm.provider import LLMProvider, ProviderConfig


class OpenAIAdapter(LLMProvider):
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ImportError(
                "OpenAIAdapter requires the optional 'openai' package to be installed."
            ) from exc
        self.client = AsyncOpenAI()
        self.model = model

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        config: ProviderConfig | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=(config.model if config and config.model else self.model),
            messages=messages,
            temperature=config.temperature if config else 0.1,
            max_tokens=config.max_tokens if config else 2048,
            response_format=(
                {"type": config.response_format}
                if config and config.response_format
                else None
            ),
        )
        content = response.choices[0].message.content or ""
        return str(content)
