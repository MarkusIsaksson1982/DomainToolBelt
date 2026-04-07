import unittest

from domaintoolbelt.core.tool_selector import VectorToolSelector, safe_parse_tool_list
from domaintoolbelt.core.types import ToolSpec


class ToolSelectorTests(unittest.IsolatedAsyncioTestCase):
    def test_safe_parse_tool_list_filters_unknown_entries(self) -> None:
        parsed = safe_parse_tool_list("['lookup_passage', 'nope']", {"lookup_passage"})
        self.assertEqual(parsed, ["lookup_passage"])

    async def test_selector_prefers_cross_reference_for_related_query(self) -> None:
        selector = VectorToolSelector(
            tools=[
                ToolSpec("lookup_passage", "Retrieve primary passages", {}),
                ToolSpec("cross_reference", "Find related cross references", {}),
                ToolSpec("theme_summary", "Summarize a theme", {}),
            ]
        )
        selected = await selector.select("find related cross references about adoption", top_k=2)
        self.assertEqual(selected[0], "cross_reference")


if __name__ == "__main__":
    unittest.main()
