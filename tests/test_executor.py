import unittest

from domaintoolbelt.core.executor import DependencyResolver
from domaintoolbelt.core.planner import HeuristicPlanner
from domaintoolbelt.domain_packs.bible_pack import BiblePack


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_dependency_resolver_groups_steps(self) -> None:
        pack = BiblePack()
        planner = HeuristicPlanner()
        steps = await planner.expand_plan(pack, type("Ctx", (), {"request": "Romans 8 adoption"})())
        clusters = DependencyResolver().resolve(steps)
        self.assertEqual(len(clusters[0].steps), 1)
        self.assertEqual(clusters[0].steps[0].step_id, "step-1")
        self.assertEqual(clusters[-1].steps[-1].step_id, "step-3")


if __name__ == "__main__":
    unittest.main()
