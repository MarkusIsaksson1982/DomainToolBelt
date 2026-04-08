from pathlib import Path
import shutil
import unittest

from domaintoolbelt.core.checkpoints import CheckpointStore
from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.core.types import StepOutcome, WorkflowContext
from domaintoolbelt.domain_packs.registry import build_pack


class ResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_kernel_resumes_from_partial_checkpoint(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_resume_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            pack = build_pack("philosophy_pack", storage_root=temp_dir)
            kernel = build_default_kernel(storage_root=temp_dir)

            ctx = WorkflowContext(request="What do philosophers say about knowledge?")
            ctx.master_plan = await kernel.planner.create_plan(pack, ctx)
            ctx.plan = await kernel.planner.expand_plan(pack, ctx)
            first_result = await pack.run_tool(
                "lookup_argument",
                "Retrieve the strongest primary sources for: What do philosophers say about knowledge?",
                {"query": "What do philosophers say about knowledge?"},
            )
            ctx.completed_steps.append(
                StepOutcome(
                    step_id="step-1",
                    description=ctx.plan[0].description,
                    tool_name="lookup_argument",
                    instruction=ctx.plan[0].instruction,
                    output=first_result.content,
                    citations=first_result.citations,
                )
            )
            await CheckpointStore(temp_dir / "checkpoints").save(ctx)

            answer = await kernel.resume(pack, ctx.session_id)

            self.assertIn("Descartes", answer)
            self.assertTrue(kernel.last_context is not None)
            self.assertEqual(kernel.last_context.session_id, ctx.session_id)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
