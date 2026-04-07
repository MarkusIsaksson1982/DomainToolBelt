from __future__ import annotations


class MCPRegistry:
    def __init__(self, pack):
        self.pack = pack

    def list_tools(self) -> list[dict[str, object]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": dict(tool.input_schema),
                "authoritative": tool.authoritative,
                "source_scope": tool.source_scope,
            }
            for tool in self.pack.config.tools
        ]
