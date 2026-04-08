from pathlib import Path
import shutil
import unittest

from domaintoolbelt.core.events import EventBus
from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.registry import build_pack


class EventBusTests(unittest.IsolatedAsyncioTestCase):
    async def test_kernel_emits_lifecycle_events(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_event_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            bus = EventBus()
            pack = build_pack("bible_pack", storage_root=temp_dir)
            kernel = build_default_kernel(storage_root=temp_dir, event_bus=bus)

            await kernel.run(pack, "What does Romans 8 say about adoption?")

            event_types = [event.event_type for event in bus.history]
            self.assertIn("run_started", event_types)
            self.assertIn("plan_created", event_types)
            self.assertIn("workflow_completed", event_types)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
