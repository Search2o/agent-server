# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.client.transports import StreamableHttpTransport
from pydantic import JsonValue

from search2o.mcpclient.mcptools import ATool


class McpClient:
    def __init__(self, url: str, headers: dict[str, JsonValue]) -> None:
        self.url = url
        self.headers = headers
        self.client: Client | None = None

    async def create(self) -> None:
        self.client = Client(StreamableHttpTransport(url=self.url, headers=self.headers))
        await self.client.__aenter__()

    async def close(self):
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception:
                pass
            finally:
                self.client = None

    async def call_tool(self, tool_name: str, args: dict[str, JsonValue]) -> CallToolResult:
        return await self.client.call_tool(tool_name, args, raise_on_error=False)

    async def list_tools(self) -> list[ATool]:
        tools = await self.client.list_tools()
        return [ATool(name=t.name, description=t.description, parameters=t.inputSchema) for t in tools]
