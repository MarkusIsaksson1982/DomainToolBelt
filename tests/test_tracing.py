from pathlib import Path
import json
import shutil
import unittest

from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.registry import build_pack


class TraceLoggerTests(unittest.IsolatedAsyncioTestCase):
    async def test_trace_logger_writes_jsonl_events(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_trace_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            pack = build_pack("bible_pack", storage_root=temp_dir)
            trace_dir = temp_dir / "traces"
            kernel = build_default_kernel(
                storage_root=temp_dir,
                enable_tracing=True,
                trace_dir=trace_dir,
            )

            await kernel.run(pack, "What does Romans 8 say about adoption?")

            session_id = kernel.last_context.session_id
            trace_path = trace_dir / f"{session_id}.jsonl"
            self.assertTrue(trace_path.exists())
            lines = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
            event_types = [line["event_type"] for line in lines]
            self.assertIn("run_started", event_types)
            self.assertIn("workflow_completed", event_types)
            self.assertTrue((trace_dir / f"{session_id}.final.txt").exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
