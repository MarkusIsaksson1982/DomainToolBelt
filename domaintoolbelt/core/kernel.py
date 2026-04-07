from __future__ import annotations

from pathlib import Path

from domaintoolbelt.core.checkpoints import CheckpointStore
from domaintoolbelt.core.executor import ParallelExecutor
from domaintoolbelt.core.guardrails import GuardrailEngine
from domaintoolbelt.core.planner import HeuristicPlanner
from domaintoolbelt.core.synthesizer import DefaultSynthesizer
from domaintoolbelt.core.tool_selector import VectorToolSelector
from domaintoolbelt.core.types import FidelityMode, WorkflowContext
from domaintoolbelt.core.validator import ValidationHub
from domaintoolbelt.rag.grounding import RAGGroundingLayer
from domaintoolbelt.rag.memory import MemoryStore


class WorkflowKernel:
    def __init__(
        self,
        planner,
        guardrails,
        selector,
        executor,
        validator,
        synthesizer,
        checkpoints,
        grounding=None,
        memory_store=None,
    ):
        self.planner = planner
        self.guardrails = guardrails
        self.selector = selector
        self.executor = executor
        self.validator = validator
        self.synthesizer = synthesizer
        self.checkpoints = checkpoints
        self.grounding = grounding
        self.memory_store = memory_store

    async def run(self, pack, request: str) -> str:
        ctx = WorkflowContext(request=request)

        if self.memory_store and pack.config.memory.enabled:
            ctx.memory_context = await self.memory_store.retrieve(
                request, top_k=pack.config.memory.max_memory_inject
            )

        ctx.retrieved_context = await pack.retrieve_context(
            request, top_k=pack.config.rag.top_k_retrieval
        )
        ctx.master_plan = await self.planner.create_plan(pack, ctx)
        ctx.master_plan = await self.guardrails.review_plan(pack, ctx)

        pending_steps = await self.planner.expand_plan(pack, ctx)
        ctx.plan = pending_steps

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
                selector=self.selector,
                validator=self.validator,
                ctx=ctx,
            )
            ctx.completed_steps.extend(results)
            await self.checkpoints.save(ctx)

            if await self.guardrails.should_stop(pack, ctx):
                break

            done_ids = {result.step_id for result in results}
            pending_steps = [step for step in pending_steps if step.step_id not in done_ids]

        answer = await self.synthesizer.write_final(pack, ctx)
        if self.grounding and pack.config.rag.enabled:
            passages = self.grounding.prepare_passages(ctx)
            report = await self.grounding.audit_synthesis(answer, passages, pack.config.fidelity.mode)
            ctx.grounding_report = report
            if not report.passed and pack.config.fidelity.mode != FidelityMode.GUIDED:
                issues = "; ".join(report.ungrounded_claims) or "Grounding audit failed."
                raise ValueError(f"Final synthesis failed grounding audit: {issues}")

        final_validation = self.validator.audit_final(pack, answer)
        if not final_validation.ok:
            raise ValueError(
                "Final synthesis failed fidelity audit: " + "; ".join(final_validation.issues)
            )

        ctx.final_answer = answer
        await self.checkpoints.save(ctx)

        if self.memory_store and pack.config.memory.enabled:
            citations = tuple(citation for step in ctx.completed_steps for citation in step.citations)
            await self.memory_store.append(ctx.session_id, request, answer, citations)

        return answer


def build_default_kernel(storage_root: str | Path = ".domaintoolbelt") -> WorkflowKernel:
    root = Path(storage_root)
    checkpoints = CheckpointStore(root / "checkpoints")
    memory_store = MemoryStore(root / "memory")
    planner = HeuristicPlanner()
    guardrails = GuardrailEngine()
    executor = ParallelExecutor()
    validator = ValidationHub()
    synthesizer = DefaultSynthesizer()
    grounding = RAGGroundingLayer()
    selector = None

    class DeferredSelector:
        async def select(self, suggestion: str, top_k: int = 12, preferred: tuple[str, ...] = ()) -> list[str]:
            nonlocal selector
            if selector is None:
                raise RuntimeError("Selector has not been initialized for the domain pack yet.")
            return await selector.select(suggestion, top_k=top_k, preferred=preferred)

    kernel = WorkflowKernel(
        planner=planner,
        guardrails=guardrails,
        selector=DeferredSelector(),
        executor=executor,
        validator=validator,
        synthesizer=synthesizer,
        checkpoints=checkpoints,
        grounding=grounding,
        memory_store=memory_store,
    )

    original_run = kernel.run

    async def _run_with_selector(pack, request: str) -> str:
        nonlocal selector
        selector = VectorToolSelector(
            tools=pack.config.tools,
            embedding_model=pack.config.tool_registry.embedding_model,
        )
        return await original_run(pack, request)

    kernel.run = _run_with_selector  # type: ignore[method-assign]
    return kernel
