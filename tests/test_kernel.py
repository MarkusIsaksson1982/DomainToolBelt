from pathlib import Path
import shutil
import unittest

from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.bible_pack import BiblePack


class KernelTests(unittest.IsolatedAsyncioTestCase):
    async def test_kernel_runs_end_to_end(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_test_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            pack = BiblePack(storage_root=temp_dir)
            kernel = build_default_kernel(storage_root=temp_dir)
            answer = await kernel.run(pack, "What does Romans 8 say about adoption?")
            self.assertIn("Romans 8", answer)
            self.assertIn("[Romans 8:15]", answer)
            checkpoint_dir = temp_dir / "checkpoints"
            self.assertTrue(any(checkpoint_dir.glob("*.json")))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
