from __future__ import annotations

from collections.abc import Mapping
import inspect
from typing import Any

from domaintoolbelt.core.types import FinalAnswer, WorkflowContext
from domaintoolbelt.domain_packs.base import has_prompts
from domaintoolbelt.llm.provider import LLMProvider, ProviderConfig, StructuredOutputError


class DefaultSynthesizer:
    async def write_final(self, pack, ctx: WorkflowContext) -> str:
        if not ctx.completed_steps:
            return "No steps were completed."

        final_step = ctx.completed_steps[-1]
        summary = self._coerce_text(final_step.output)
        supporting = [self._coerce_text(step.output) for step in ctx.completed_steps[:-1]]

        citations: list[str] = []
        for step in ctx.completed_steps:
            citations.extend(step.citations)

        unique_citations: list[str] = []
        for citation in citations:
            if citation not in unique_citations:
                unique_citations.append(citation)

        lines = [summary]
        if supporting:
            lines.append("")
            lines.append("Supporting notes:")
            lines.extend(f"- {note}" for note in supporting if note)
        if unique_citations:
            lines.append("")
            lines.append("Citations: " + ", ".join(f"[{citation}]" for citation in unique_citations))
        return "\n".join(lines).strip()

    @staticmethod
    def _coerce_text(output: Any) -> str:
        if isinstance(output, str):
            return output
        if isinstance(output, Mapping):
            if "summary" in output:
                return str(output["summary"])
            return "; ".join(f"{key}: {value}" for key, value in output.items())
        if isinstance(output, (list, tuple)):
            return "; ".join(DefaultSynthesizer._coerce_text(item) for item in output)
        return str(output)


class LLMSynthesizer(DefaultSynthesizer):
    def __init__(self, provider: LLMProvider | None = None, warning_callback=None) -> None:
        self.provider = provider
        self.warning_callback = warning_callback

    async def write_final(self, pack, ctx: WorkflowContext) -> FinalAnswer | str:
        if not (self.provider and has_prompts(pack) and pack.config.llm.enabled):
            return await super().write_final(pack, ctx)

        evidence = self._serialize_evidence(ctx)
        prompt = pack.load_prompt(
            "write_final_answer.md",
            request=ctx.request,
            evidence=evidence,
        )
        if pack.config.llm.structured_output:
            prompt += (
                "\n\nReturn a JSON object with these fields: "
                "answer, citations, confidence, issues, metadata."
            )
        try:
            if pack.config.llm.structured_output:
                response = await self.provider.structured(
                    prompt,
                    schema={
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string"},
                            "citations": {"type": "array", "items": {"type": "string"}},
                            "confidence": {"type": "number"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "metadata": {"type": "object"},
                        },
                        "required": ["answer", "citations"],
                    },
                    system=_load_optional_prompt(pack, "supervisor.md"),
                    config=ProviderConfig(
                        model=pack.config.llm.synthesizer_model,
                        temperature=pack.config.llm.temperature,
                        max_tokens=pack.config.llm.max_tokens,
                        response_format="json_object",
                        metadata={"pack": pack.config.key, "phase": "synthesis"},
                    ),
                )
                return _coerce_final_answer(response)
            response = await self.provider.complete(
                prompt,
                system=_load_optional_prompt(pack, "supervisor.md"),
                config=ProviderConfig(
                    model=pack.config.llm.synthesizer_model,
                    temperature=pack.config.llm.temperature,
                    max_tokens=pack.config.llm.max_tokens,
                    metadata={"pack": pack.config.key, "phase": "synthesis"},
                ),
            )
        except StructuredOutputError:
            await self._emit_warning(
                ctx,
                "synthesizer",
                "Final answer structured output was invalid; falling back to text synthesis.",
            )
            if not pack.config.llm.structured_fallback:
                raise
            return await super().write_final(pack, ctx)
        except Exception:
            await self._emit_warning(
                ctx,
                "synthesizer",
                "Final answer LLM call failed; falling back to text synthesis.",
            )
            return await super().write_final(pack, ctx)

        cleaned = response.strip()
        return cleaned or await super().write_final(pack, ctx)

    def _serialize_evidence(self, ctx: WorkflowContext) -> str:
        lines: list[str] = []
        for step in ctx.completed_steps:
            lines.append(f"{step.step_id}: {step.description}")
            lines.append(self._coerce_text(step.output))
            if step.citations:
                lines.append("Citations: " + ", ".join(f"[{item}]" for item in step.citations))
            lines.append("")
        return "\n".join(lines).strip()

    async def _emit_warning(self, ctx: WorkflowContext, phase: str, message: str) -> None:
        if not self.warning_callback:
            return
        result = self.warning_callback(ctx, phase, message)
        if inspect.isawaitable(result):
            await result


def _coerce_final_answer(payload: Any) -> FinalAnswer:
    if isinstance(payload, FinalAnswer):
        return payload
    if not isinstance(payload, Mapping):
        raise StructuredOutputError("Synthesizer structured output must be a mapping.")

    answer = str(payload.get("answer") or "").strip()
    if not answer:
        raise StructuredOutputError("Synthesizer structured output is missing 'answer'.")
    citations = payload.get("citations", ())
    issues = payload.get("issues", ())
    confidence = payload.get("confidence")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (TypeError, ValueError) as exc:
            raise StructuredOutputError("Synthesizer 'confidence' must be numeric.") from exc
    return FinalAnswer(
        answer=answer,
        citations=tuple(str(item) for item in citations) if isinstance(citations, (list, tuple)) else (),
        confidence=confidence,
        issues=tuple(str(item) for item in issues) if isinstance(issues, (list, tuple)) else (),
        metadata=dict(payload.get("metadata", {})) if isinstance(payload.get("metadata"), Mapping) else {},
    )


def _load_optional_prompt(pack: Any, filename: str) -> str | None:
    try:
        return pack.load_prompt(filename)
    except FileNotFoundError:
        return None
