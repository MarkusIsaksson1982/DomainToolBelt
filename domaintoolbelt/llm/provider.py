from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from typing import Any, Mapping


@dataclass(frozen=True)
class ProviderConfig:
    model: str = ""
    temperature: float = 0.1
    max_tokens: int = 2048
    response_format: str | None = None
    metadata: Mapping[str, Any] | None = None


class StructuredOutputError(ValueError):
    pass


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        config: ProviderConfig | None = None,
    ) -> str:
        raise NotImplementedError

    async def structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
        config: ProviderConfig | None = None,
    ) -> Any:
        schema_hint = json.dumps(schema, indent=2, sort_keys=True)
        raw = await self.complete(
            prompt=(
                f"{prompt}\n\n"
                "Return valid JSON that matches this schema exactly.\n"
                f"{schema_hint}"
            ),
            system=system,
            config=config,
        )
        try:
            return _extract_json_value(raw)
        except ValueError as exc:
            raise StructuredOutputError(str(exc)) from exc


def _extract_json_value(raw: str) -> Any:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Provider returned empty structured output.")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = min((index for index in (raw.find("{"), raw.find("[")) if index >= 0), default=-1)
    if start < 0:
        raise ValueError("Provider did not return JSON content.")

    for end in range(len(raw), start, -1):
        fragment = raw[start:end].strip()
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            continue
    raise ValueError("Provider JSON output could not be parsed.")
