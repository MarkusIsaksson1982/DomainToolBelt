from __future__ import annotations

from typing import Any, Mapping

from domaintoolbelt.mcp.registry import MCPRegistry


class DomainPackServer:
    def __init__(self, pack):
        self.pack = pack
        self.registry = MCPRegistry(pack)

    async def handle(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        method = payload.get("method")
        if method == "tools/list":
            return {"tools": self.registry.list_tools()}
        if method == "tools/call":
            result = await self.pack.run_tool(
                payload["tool_name"],
                payload.get("instruction", ""),
                payload.get("arguments", {}),
            )
            return {"result": result}
        raise ValueError(f"Unsupported method: {method}")
