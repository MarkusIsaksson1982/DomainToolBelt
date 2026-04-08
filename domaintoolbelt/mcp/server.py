from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from domaintoolbelt.core.types import ToolResult
from domaintoolbelt.mcp.registry import MCPRegistry


class DomainPackServer:
    def __init__(self, pack, kernel=None, session_root: str | Path | None = None):
        self.pack = pack
        self.kernel = kernel
        self.registry = MCPRegistry(pack)
        self.session_root = Path(session_root) if session_root else None
        self._sessions: dict[str, dict[str, Any]] = {}
        if self.session_root:
            self.session_root.mkdir(parents=True, exist_ok=True)
            self._sessions = self._load_sessions()

    async def handle(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        method = str(payload.get("method") or "")
        session_id = str(payload.get("session_id") or "default")

        if method == "initialize":
            return {
                "server": {
                    "name": "domaintoolbelt",
                    "version": self.pack.config.version,
                    "pack": self.pack.config.key,
                },
                "capabilities": {
                    "tools": True,
                    "workflow": self.kernel is not None,
                    "sessions": True,
                },
            }
        if method == "tools/list":
            return {
                "tools": self.registry.list_tools(),
                "pack": {
                    "key": self.pack.config.key,
                    "display_name": self.pack.config.display_name,
                },
            }
        if method == "tools/call":
            return await self._handle_tool_call(payload, session_id)
        if method in {"query/run", "answer_query"}:
            return await self._handle_query_run(payload, session_id)
        if method == "session/status":
            return self._get_session_status(session_id)
        if method == "session/resume":
            return await self._handle_session_resume(session_id)
        raise ValueError(f"Unsupported method: {method}")

    async def _handle_tool_call(
        self,
        payload: Mapping[str, Any],
        session_id: str,
    ) -> Mapping[str, Any]:
        tool_name = str(payload.get("tool_name") or "")
        if not tool_name:
            return {"error": "Missing 'tool_name' field.", "session_id": session_id}

        result = await self.pack.run_tool(
            tool_name,
            str(payload.get("instruction") or ""),
            payload.get("arguments", {}),
        )
        rendered = self._serialize_result(result)
        session = self._sessions.setdefault(session_id, {})
        session["last_tool_result"] = rendered
        self._persist_session(session_id)
        return {"result": rendered, "session_id": session_id}

    async def _handle_query_run(
        self,
        payload: Mapping[str, Any],
        session_id: str,
    ) -> Mapping[str, Any]:
        if not self.kernel:
            return {"error": "Kernel is not attached to the MCP server.", "session_id": session_id}

        query = str(payload.get("query") or "")
        if not query:
            return {"error": "Missing 'query' field.", "session_id": session_id}

        answer = await self.kernel.run(self.pack, query)
        workflow_session_id = self.kernel.last_context.session_id if self.kernel.last_context else ""
        self._sessions[session_id] = {
            "query": query,
            "answer": answer,
            "pack": self.pack.config.key,
            "workflow_session_id": workflow_session_id,
        }
        self._persist_session(session_id)
        return {
            "answer": answer,
            "session_id": session_id,
            "workflow_session_id": workflow_session_id,
        }

    async def _handle_session_resume(self, session_id: str) -> Mapping[str, Any]:
        if not self.kernel:
            return {"error": "Kernel is not attached to the MCP server.", "session_id": session_id}

        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Unknown session.", "session_id": session_id}

        workflow_session_id = str(session.get("workflow_session_id") or "")
        if not workflow_session_id:
            return {"error": "Session does not have a workflow checkpoint.", "session_id": session_id}

        answer = await self.kernel.resume(self.pack, workflow_session_id)
        session["answer"] = answer
        self._persist_session(session_id)
        return {
            "answer": answer,
            "session_id": session_id,
            "workflow_session_id": workflow_session_id,
        }

    def _get_session_status(self, session_id: str) -> Mapping[str, Any]:
        session = self._sessions.get(session_id, {})
        return {
            "session_id": session_id,
            "found": bool(session),
            "pack": session.get("pack", self.pack.config.key),
            "query": session.get("query", ""),
            "answer": session.get("answer", ""),
            "workflow_session_id": session.get("workflow_session_id", ""),
        }

    @staticmethod
    def _serialize_result(result: Any) -> Any:
        if isinstance(result, ToolResult):
            return {
                "content": result.content,
                "citations": list(result.citations),
                "issues": list(result.issues),
                "metadata": dict(result.metadata),
            }
        return result

    def _persist_session(self, session_id: str) -> None:
        if not self.session_root:
            return
        path = self.session_root / f"{session_id}.json"
        path.write_text(json.dumps(self._sessions[session_id], indent=2), encoding="utf-8")

    def _load_sessions(self) -> dict[str, dict[str, Any]]:
        sessions: dict[str, dict[str, Any]] = {}
        for path in self.session_root.glob("*.json"):
            try:
                sessions[path.stem] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
        return sessions
