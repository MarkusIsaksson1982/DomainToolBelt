from pathlib import Path
import shutil
import unittest

from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.core.types import FidelityMode
from domaintoolbelt.domain_packs.bible_pack import BiblePack


class _UnsupportedSynthesizer:
    async def write_final(self, pack, ctx):
        return "This unsupported conclusion has no basis in the retrieved passages."


class GroundingTests(unittest.IsolatedAsyncioTestCase):
    async def test_strict_mode_raises_on_ungrounded_claim(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_grounding_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            pack = BiblePack(storage_root=temp_dir)
            pack.config.rag.fidelity_mode = FidelityMode.STRICT
            kernel = build_default_kernel(storage_root=temp_dir)
            kernel.synthesizer = _UnsupportedSynthesizer()

            with self.assertRaisesRegex(ValueError, "grounding audit"):
                await kernel.run(pack, "What does Romans 8 say about adoption?")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
