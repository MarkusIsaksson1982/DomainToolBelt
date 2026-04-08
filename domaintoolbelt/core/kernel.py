from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from domaintoolbelt.core.checkpoints import CheckpointStore
from domaintoolbelt.core.events import (
    CheckpointSavedEvent,
    ContextRetrievedEvent,
    EventBus,
    PlanCreatedEvent,
    ReviewRequiredEvent,
    RunResumedEvent,
    RunStartedEvent,
    ValidationWarningEvent,
    WorkflowCompletedEvent,
)
from domaintoolbelt.core.executor import ParallelExecutor
from domaintoolbelt.core.guardrails import GuardrailEngine
from domaintoolbelt.core.planner import LLMPlanner
from domaintoolbelt.core.synthesizer import LLMSynthesizer
from domaintoolbelt.core.tool_selector import PromptToolReranker, VectorToolSelector
from domaintoolbelt.core.types import FidelityMode, FinalAnswer, WorkflowContext
from domaintoolbelt.core.validator import ValidationHub
from domaintoolbelt.llm.provider import LLMProvider
from domaintoolbelt.observability.logger import TraceLogger
from domaintoolbelt.rag.citations import extract_citations
from domaintoolbelt.rag.grounding import RAGGroundingLayer
from domaintoolbelt.rag.memory import MemoryStore


SelectorFactory = Callable[[Any], Any]


class WorkflowKernel:
    def __init__(
        self,
        planner,
        guardrails,
        selector_factory: SelectorFactory,
        executor,
        validator,
        synthesizer,
        checkpoints,
        grounding=None,
        memory_store=None,
        event_bus: EventBus | None = None,
    ):
        self.planner = planner
        self.guardrails = guardrails
        self.selector_factory = selector_factory
        self.executor = executor
        self.validator = validator
        self.synthesizer = synthesizer
        self.checkpoints = checkpoints
        self.grounding = grounding
        self.memory_store = memory_store
        self.event_bus = event_bus or EventBus()
        self.last_context: WorkflowContext | None = None

    async def run(self, pack, request: str) -> str:
        ctx = WorkflowContext(request=request)
        self.last_context = ctx
        selector = self.selector_factory(pack)

        await self.event_bus.emit(
            RunStartedEvent(
                event_type="run_started",
                session_id=ctx.session_id,
                request=request,
                pack_key=pack.config.key,
            )
        )

        if self.memory_store and pack.config.memory.enabled:
            self.memory_store.decay_half_life_days = pack.config.memory.decay_half_life_days
            ctx.memory_context = await self.memory_store.retrieve(
                request, top_k=pack.config.memory.max_memory_inject
            )

        ctx.retrieved_context = await pack.retrieve_context(
            request, top_k=pack.config.rag.top_k_retrieval
        )
        await self.event_bus.emit(
            ContextRetrievedEvent(
                event_type="context_retrieved",
                session_id=ctx.session_id,
                retrieved_count=len(ctx.retrieved_context),
                memory_count=len(ctx.memory_context),
            )
        )

        ctx.master_plan = await self.planner.create_plan(pack, ctx)
        ctx.master_plan = await self.guardrails.review_plan(pack, ctx)

        ctx.plan = await self.planner.expand_plan(pack, ctx)
        await self.event_bus.emit(
            PlanCreatedEvent(
                event_type="plan_created",
                session_id=ctx.session_id,
                master_plan=ctx.master_plan,
                step_ids=tuple(step.step_id for step in ctx.plan),
            )
        )
        return await self._execute_pending(pack, ctx, selector)

    async def resume(self, pack, session_id: str) -> str:
        ctx = self.checkpoints.restore(session_id)
        self.last_context = ctx
        selector = self.selector_factory(pack)
        if self.memory_store and pack.config.memory.enabled:
            self.memory_store.decay_half_life_days = pack.config.memory.decay_half_life_days
            if not ctx.memory_context:
                ctx.memory_context = await self.memory_store.retrieve(
                    ctx.request, top_k=pack.config.memory.max_memory_inject
                )
        if not ctx.retrieved_context:
            ctx.retrieved_context = await pack.retrieve_context(
                ctx.request, top_k=pack.config.rag.top_k_retrieval
            )
        await self.event_bus.emit(
            RunResumedEvent(
                event_type="run_resumed",
                session_id=ctx.session_id,
                request=ctx.request,
                pack_key=pack.config.key,
            )
        )
        await self.event_bus.emit(
            ContextRetrievedEvent(
                event_type="context_retrieved",
                session_id=ctx.session_id,
                retrieved_count=len(ctx.retrieved_context),
                memory_count=len(ctx.memory_context),
            )
        )
        await self.event_bus.emit(
            PlanCreatedEvent(
                event_type="plan_created",
                session_id=ctx.session_id,
                master_plan=ctx.master_plan,
                step_ids=tuple(step.step_id for step in ctx.plan),
            )
        )
        if ctx.final_answer:
            return ctx.final_answer
        return await self._execute_pending(pack, ctx, selector)

    async def _execute_pending(self, pack, ctx: WorkflowContext, selector: Any) -> str:
        completed_ids = {result.step_id for result in ctx.completed_steps}
        pending_steps = [step for step in ctx.plan if step.step_id not in completed_ids]

        while pending_steps:
            ready_steps = self.executor.ready_steps(
                pending_steps=pending_steps,
                completed_steps=ctx.completed_steps,
                max_parallel_steps=pack.config.max_parallel_steps,
            )
            if not ready_steps:
                raise ValueError("No executable steps remain; the dependency graph may be invalid.")

            results = await self.executor.run_steps(
                pack=pack,
                steps=ready_steps,
                selector=selector,
                validator=self.validator,
                ctx=ctx,
                event_bus=self.event_bus,
            )
            ctx.completed_steps.extend(results)
            await self._save_checkpoint(ctx)

            if await self.guardrails.should_stop(pack, ctx):
                await self.event_bus.emit(
                    ReviewRequiredEvent(
                        event_type="review_required",
                        session_id=ctx.session_id,
                        step_id=ctx.completed_steps[-1].step_id,
                        reason="Partner review trigger matched the latest step output.",
                    )
                )
                break

            done_ids = {result.step_id for result in results}
            pending_steps = [step for step in pending_steps if step.step_id not in done_ids]

        return await self._finalize(pack, ctx)

    async def _finalize(self, pack, ctx: WorkflowContext) -> str:
        synthesis = await self.synthesizer.write_final(pack, ctx)
        final_payload = self._coerce_final_payload(ctx, synthesis)
        answer_text = final_payload.answer

        if self.grounding and pack.config.rag.enabled:
            passages = self.grounding.prepare_passages(ctx)
            report = await self.grounding.audit_synthesis(
                answer_text,
                passages,
                pack.config.rag.fidelity_mode,
                similarity_threshold=pack.config.rag.similarity_threshold,
            )
            ctx.grounding_report = report
            if not report.passed and pack.config.rag.fidelity_mode != FidelityMode.GUIDED:
                issues = "; ".join(report.ungrounded_claims) or "Grounding audit failed."
                raise ValueError(f"Final synthesis failed grounding audit: {issues}")

        final_validation = self.validator.audit_final(pack, answer_text, final_payload.citations)
        if not final_validation.ok:
            raise ValueError(
                "Final synthesis failed fidelity audit: " + "; ".join(final_validation.issues)
            )

        ctx.final_answer = answer_text
        ctx.final_payload = final_payload
        await self._save_checkpoint(ctx)

        if self.memory_store and pack.config.memory.enabled:
            await self.memory_store.append(
                ctx.session_id,
                ctx.request,
                answer_text,
                final_payload.citations,
            )

        await self.event_bus.emit(
            WorkflowCompletedEvent(
                event_type="workflow_completed",
                session_id=ctx.session_id,
                final_answer=answer_text,
            )
        )
        return answer_text

    async def _save_checkpoint(self, ctx: WorkflowContext) -> None:
        checkpoint_path = await self.checkpoints.save(ctx)
        await self.event_bus.emit(
            CheckpointSavedEvent(
                event_type="checkpoint_saved",
                session_id=ctx.session_id,
                path=str(checkpoint_path),
            )
        )

    def _coerce_final_payload(self, ctx: WorkflowContext, synthesis: FinalAnswer | str) -> FinalAnswer:
        if isinstance(synthesis, FinalAnswer):
            citations = synthesis.citations or self._collect_step_citations(ctx)
            return FinalAnswer(
                answer=synthesis.answer,
                citations=citations,
                confidence=synthesis.confidence,
                issues=synthesis.issues,
                metadata=dict(synthesis.metadata),
            )

        answer = str(synthesis)
        citations = extract_citations(answer) or self._collect_step_citations(ctx)
        return FinalAnswer(answer=answer, citations=citations)

    @staticmethod
    def _collect_step_citations(ctx: WorkflowContext) -> tuple[str, ...]:
        citations: list[str] = []
        for step in ctx.completed_steps:
            for citation in step.citations:
                if citation not in citations:
                    citations.append(citation)
        return tuple(citations)


def build_default_kernel(
    storage_root: str | Path = ".domaintoolbelt",
    llm_provider: LLMProvider | None = None,
    event_bus: EventBus | None = None,
    enable_tracing: bool = False,
    trace_dir: str | Path | None = None,
) -> WorkflowKernel:
    root = Path(storage_root)
    bus = event_bus or EventBus()
    if enable_tracing:
        TraceLogger(trace_dir or root / "traces").attach(bus)

    checkpoints = CheckpointStore(root / "checkpoints")
    memory_store = MemoryStore(
        root / "memory",
        decay_half_life_days=30.0,
    )

    async def _emit_warning(ctx: WorkflowContext, phase: str, message: str) -> None:
        await bus.emit(
            ValidationWarningEvent(
                event_type="validation_warning",
                session_id=ctx.session_id,
                phase=phase,
                message=message,
            )
        )

    planner = LLMPlanner(provider=llm_provider, warning_callback=_emit_warning)
    guardrails = GuardrailEngine()
    executor = ParallelExecutor()
    validator = ValidationHub()
    synthesizer = LLMSynthesizer(provider=llm_provider, warning_callback=_emit_warning)
    grounding = RAGGroundingLayer()

    def _build_selector(pack: Any) -> VectorToolSelector:
        reranker = None
        if llm_provider and pack.config.llm.enabled:
            reranker = PromptToolReranker(llm_provider, pack)
        return VectorToolSelector(
            tools=pack.config.tools,
            embedding_model=pack.config.tool_registry.embedding_model,
            reranker=reranker,
        )

    return WorkflowKernel(
        planner=planner,
        guardrails=guardrails,
        selector_factory=_build_selector,
        executor=executor,
        validator=validator,
        synthesizer=synthesizer,
        checkpoints=checkpoints,
        grounding=grounding,
        memory_store=memory_store,
        event_bus=bus,
    )
