from __future__ import annotations

from domaintoolbelt.core.types import WorkflowContext


class GuardrailEngine:
    async def review_plan(self, pack, ctx: WorkflowContext) -> str:
        notes: list[str] = []
        if pack.config.guardrails.tradition_flags:
            serialized = ", ".join(
                f"{key}={value}" for key, value in pack.config.guardrails.tradition_flags.items()
            )
            notes.append(f"Tradition flags: {serialized}")
        if pack.config.fidelity.require_citations:
            notes.append("Citations are mandatory in grounded outputs.")
        if pack.config.guardrails.require_primary_source:
            notes.append("Prefer primary-source evidence over commentary.")

        ctx.guardrail_notes = notes
        if not notes:
            return ctx.master_plan

        return f"{ctx.master_plan}\n\nGuardrails:\n" + "\n".join(f"- {note}" for note in notes)

    async def should_stop(self, pack, ctx: WorkflowContext) -> bool:
        if not ctx.completed_steps:
            return False
        if pack.config.guardrails.partner_mode_enabled:
            last_output = ctx.completed_steps[-1].output
            serialized = str(last_output).lower()
            for trigger in pack.config.guardrails.partner_mode_triggers:
                if trigger.lower() in serialized:
                    return True
        return False
