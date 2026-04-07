from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from domaintoolbelt.core.types import WorkflowContext


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
