from pathlib import Path
import shutil
import unittest

from domaintoolbelt.domain_packs.registry import build_pack, list_pack_keys


class RegistryTests(unittest.TestCase):
    def test_builtin_packs_are_discoverable(self) -> None:
        packs = list_pack_keys()
        self.assertIn("bible_pack", packs)
        self.assertIn("legal_pack", packs)
        self.assertIn("philosophy_pack", packs)

    def test_build_pack_returns_requested_pack(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_registry_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            pack = build_pack("legal_pack", storage_root=temp_dir)
            self.assertEqual(pack.config.key, "legal_pack")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
