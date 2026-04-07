from pathlib import Path
import unittest

from domaintoolbelt.core.prompt_loader import PromptLoader


class PromptLoaderTests(unittest.TestCase):
    def test_prompt_loader_renders_variables(self) -> None:
        prompt_dir = (
            Path(__file__).resolve().parents[1]
            / "domaintoolbelt"
            / "domain_packs"
            / "bible_pack"
            / "prompts"
        )
        loader = PromptLoader(prompt_dir)
        content = loader.load("tool_instruction.md", step_description="Inspect adoption", request="Romans 8")
        self.assertIn("Inspect adoption", content)
        self.assertIn("Romans 8", content)


if __name__ == "__main__":
    unittest.main()
