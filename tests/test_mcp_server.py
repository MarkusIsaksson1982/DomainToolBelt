from pathlib import Path
import shutil
import unittest

from domaintoolbelt.core.kernel import build_default_kernel
from domaintoolbelt.domain_packs.registry import build_pack
from domaintoolbelt.mcp.server import DomainPackServer


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_server_initializes_and_runs_query(self) -> None:
        temp_dir = Path(__file__).resolve().parents[1] / ".tmp_mcp_state"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            pack = build_pack("legal_pack", storage_root=temp_dir)
            kernel = build_default_kernel(storage_root=temp_dir)
            server = DomainPackServer(pack, kernel=kernel)

            initialize = await server.handle({"method": "initialize"})
            self.assertEqual(initialize["server"]["pack"], "legal_pack")

            response = await server.handle(
                {
                    "method": "query/run",
                    "session_id": "session-1",
                    "query": "What does the GDPR say about access requests?",
                }
            )
            self.assertIn("GDPR Art. 12", response["answer"])
            self.assertTrue(response["workflow_session_id"])

            status = await server.handle({"method": "session/status", "session_id": "session-1"})
            self.assertTrue(status["found"])
            self.assertIn("access requests", status["query"])
            self.assertEqual(status["workflow_session_id"], response["workflow_session_id"])

            resumed = await server.handle({"method": "session/resume", "session_id": "session-1"})
            self.assertIn("GDPR Art. 12", resumed["answer"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
