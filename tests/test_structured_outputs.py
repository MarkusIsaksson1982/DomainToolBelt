from pathlib import Path
import shutil
import unittest

from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.registry import build_pack
from domaintoolbelt.llm.provider import LLMProvider


class FakeStructuredProvider(LLMProvider):
    async def complete(self, prompt: str, system: str | None = None, config=None) -> str:
        return "unused"

    async def structured(self, prompt: str, schema: dict, system: str | None = None, config=None):
        if "tool_names" in schema.get("properties", {}):
            return {"tool_names": ["lookup_passage", "cross_reference", "theme_summary"]}
        if "steps" in schema.get("properties", {}):
            return {
                "steps": [
                    {
                        "step_id": "step-1",
                        "description": "Gather the most relevant primary sources.",
                        "instruction": "Retrieve the strongest primary sources for: What does Romans 8 say about adoption?",
                        "depends_on": [],
                        "preferred_tools": ["lookup_passage"],
                        "tool_name": "",
                        "tool_args": {"query": "What does Romans 8 say about adoption?"},
                    },
                    {
                        "step_id": "step-2",
                        "description": "Find cross references that reinforce or clarify the primary sources.",
                        "instruction": "Find grounded cross references that speak to: What does Romans 8 say about adoption?",
                        "depends_on": ["step-1"],
                        "preferred_tools": [],
                        "tool_name": "cross_reference",
                        "tool_args": {"seed_summary": "$step-1.summary"},
                    },
                    {
                        "step_id": "step-3",
                        "description": "Synthesize a domain-grounded summary from the gathered evidence.",
                        "instruction": "Write a concise, citation-rich synthesis for: What does Romans 8 say about adoption?",
                        "depends_on": ["step-1", "step-2"],
                        "preferred_tools": [],
                        "tool_name": "theme_summary",
                        "tool_args": {"primary": "$step-1.summary", "secondary": "$step-2.summary"},
                    },
                ]
            }
        return {
            "answer": (
                "Romans 8 presents adoption as Spirit-enabled sonship [Romans 8:15][Romans 8:16][Romans 8:17]."
            ),
            "citations": ["Romans 8:15", "Romans 8:16", "Romans 8:17"],
            "confidence": 0.9,
            "issues": [],
            "metadata": {"mode": "structured-test"},
        }


class StructuredOutputTests(unittest.IsolatedAsyncioTestCase):
    async def test_kernel_preserves_structured_final_payload(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_structured_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            pack = build_pack("bible_pack", storage_root=temp_dir)
            pack.config.llm.structured_output = True
            kernel = build_default_kernel(
                storage_root=temp_dir,
                llm_provider=FakeStructuredProvider(),
            )

            answer = await kernel.run(pack, "What does Romans 8 say about adoption?")

            self.assertIn("Romans 8 presents adoption", answer)
            self.assertIsNotNone(kernel.last_context.final_payload)
            self.assertEqual(kernel.last_context.final_payload.confidence, 0.9)
            self.assertIn("Romans 8:15", kernel.last_context.final_payload.citations)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
