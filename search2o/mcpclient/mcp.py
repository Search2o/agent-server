# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from typing import Any

from mcp import McpError
from mcp.types import ContentBlock
from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import SERVICE_RETRY, ShowMessage
from search2o.common.sensitivestring import SensitiveString
from search2o.common.toolresponse import ToolResponse
from search2o.execution.streamiter import StreamIter
from search2o.mcpclient.mcpclient import McpClient
from search2o.models.prompt import McpToolModel, AMcpToolResult, McpToolResult
from search2o.models.systemconfig import McpServerModel


def error_text(e: BaseException) -> str:
    if isinstance(e, BaseExceptionGroup):
        return "; ".join(error_text(sub) for sub in e.exceptions)
    return f"{type(e).__name__}: {e}"


class Mcp:

    def __init__(self, mcp_server: McpServerModel, headers: dict[str, JsonValue]) -> None:
        super().__init__()
        self.mcp_server = mcp_server
        self.mcp_name = mcp_server.name
        self.client = McpClient(url=mcp_server.url, headers=headers)
        self.mcp_tools: dict[str, McpToolModel] = {}  # mcp_server.tool_name -> tool

    async def _init(self, stream_iter: StreamIter):
        stream_iter.trace(lambda: f"Creating connection to MCP server {self.mcp_name}: {self.mcp_server.url}", TraceType.tool)
        try:
            await self.client.create()
        except (Exception, BaseExceptionGroup) as e:
            await self.client.close()
            self.client = None
            stream_iter.trace(lambda e=e: f"Exception while creating connection to MCP server: {error_text(e)}", TraceType.error)
            raise ShowMessage(f"Could not establish a connection to MCP server {self.mcp_name}", SERVICE_RETRY)

        try:
            resp = await self.client.list_tools()
        except (Exception, BaseExceptionGroup) as e:
            await self.client.close()
            self.client = None
            stream_iter.trace(lambda e=e: f"Exception while listing tools from MCP server: {error_text(e)}", TraceType.error)
            raise ShowMessage(f"Error listing tools from MCP server {self.mcp_name}", SERVICE_RETRY)
        if resp:
            for atool in resp:
                full_name = self._full_name(self.mcp_name, atool.name)
                toolm = McpToolModel(name=full_name, description=atool.description or "", parameters=atool.parameters)
                self.mcp_tools[full_name] = toolm
            if stream_iter.should_trace:
                stream_iter.trace(lambda: f"MCP {self.mcp_name} returned the following tools: {', '.join([atool.name for atool in resp])}", TraceType.tool)
        else:
            await self.client.close()
            self.client = None
            raise ShowMessage(f"MCP server {self.mcp_name} returned an empty tool list", SERVICE_RETRY)

    @staticmethod
    async def create(mcp_server: McpServerModel, headers: dict[str, JsonValue], stream_iter: StreamIter) -> Mcp:
        registry = Mcp(mcp_server, headers)
        await registry._init(stream_iter)
        return registry

    async def close(self):
        if self.client:
            await self.client.close()
            self.client = None

    @staticmethod
    def _full_name(mcp_name: str, tool_name: str) -> str:
        return f"{AgentWords.mcp}_{mcp_name}_{tool_name}"

    @staticmethod
    def get_split_name(full_name: str) -> tuple[str, str]:
        prefix, _, tool_name = full_name.partition("_")
        return prefix, tool_name

    def get_tool(self, tool_name: str) -> McpToolModel | None:
        tool_name = self._full_name(self.mcp_name, tool_name)
        return self.mcp_tools.get(tool_name)

    def get_all_tools(self):
        return self.mcp_tools.values()

    @staticmethod
    def _flatten_for_llm(content: list[ContentBlock]) -> dict[str, Any]:
        out: list[AMcpToolResult] = []
        for b in content:
            t = b.type
            if t == "text":
                out.append(AMcpToolResult(contentType="text", content=b.text).model_dump())
            elif t == "image":
                out.append(AMcpToolResult(contentType="image", content=b.data, mimeType=b.mimeType).model_dump())
            elif t == "audio":
                out.append(AMcpToolResult(contentType="audio", content="This embedded resource has been omitted", mimeType=b.mimeType).model_dump())
            elif t == "resource_link":
                if b.uri:
                    out.append(AMcpToolResult(contentType="URI", content=f"Resource available at {b.uri}. {b.description}. The resource content has been omitted.").model_dump())
            elif t == "resource":
                out.append(AMcpToolResult(contentType="resource", content="This embedded resource has been omitted").model_dump())
        return McpToolResult(content=out).model_dump()

    @staticmethod
    def _get_error_message(content: list[ContentBlock]) -> str:
        if content and content[0].type == "text" and content[0].text:
            return content[0].text
        else:
            return "Unknown error"


    async def call_tool(self, tool_name: str, args: dict[str, JsonValue], stream_iter: StreamIter) -> ToolResponse:
        try:
            result = await self.client.call_tool(tool_name, args)
            if result.is_error:
                error_message = self._get_error_message(result.content)
                stream_iter.trace(lambda: f"MCP server returned an error message when calling MCP tool {self.mcp_name}.{tool_name} with args {args}: {error_message}", TraceType.error)
                return ToolResponse(recoverable=True, error_message=error_message)
            elif result.structured_content:
                stream_iter.trace(lambda: f"MCP server returned a tool response: {result.structured_content}", TraceType.tool)
                return ToolResponse(success=True, response=result.structured_content)
            else:
                stream_iter.trace(lambda: f"MCP server returned content: {result.content}", TraceType.tool)
                return ToolResponse(success=True, response=self._flatten_for_llm(result.content))
        except McpError as e:
            if e.error.message:
                recoverable = e.error.code in self.mcp_server.retryableErrorCodes
                stream_iter.trace(lambda e=e: f"MCP server responded with error when calling MCP tool {self.mcp_name}.{tool_name} with args {args}: Error Code - {e.error.code}, Error Message - {e.error.message}", TraceType.error)
                return ToolResponse(recoverable=recoverable, error_message=f"Error calling MCP tool {self.mcp_name}.{tool_name}: {e.error.message}")
            else:
                stream_iter.trace(lambda: f"Irrecoverable error when calling MCP tool {self.mcp_name}.{tool_name} with args {args}", TraceType.error)
                return ToolResponse(recoverable=False, error_message=f"Irrecoverable error when calling MCP tool {self.mcp_name}.{tool_name}.")
        except (Exception, BaseExceptionGroup) as e:
            stream_iter.trace(lambda e=e: f"Exception calling MCP tool {self.mcp_name}.{tool_name} with args {args}: {error_text(e)}", TraceType.error)
            return ToolResponse(recoverable=False, error_message=f"Exception calling MCP tool {self.mcp_name}.{tool_name}: {SensitiveString.safe_text(error_text(e))}")


