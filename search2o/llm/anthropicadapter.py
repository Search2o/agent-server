# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import json
from typing import Any

from pydantic import JsonValue

from search2o.llm.basellmadapter import BaseLlmAdapter
from search2o.llm.schemabuilder import SchemaBuilder
from search2o.models.prompt import ToolCall, ContentOutput, TextPart, ToolCalls, \
    PromptElement, ImagePart, LlmResponseModel, LlmRequestModel


class AnthropicAdapter(BaseLlmAdapter):
    def name(self) -> str:
        return "anthropic"

    def description(self) -> str:
        return "Adapter for Anthropic or any vendor that is compatible with it"

    def set_model(self, req: LlmRequestModel, params: dict[str, Any]):
        params["model"] = req.model

    def set_max_tokens(self, req: LlmRequestModel, params: dict[str, Any]):
        params["max_tokens"] = req.maxTokens

    def set_tools(self, req: LlmRequestModel, params: dict[str, Any]) -> None:
        tm = []

        for tool in req.vendorTools:
            tm.append(tool)

        if req.mcpTools:
            for tool in req.mcpTools:
                tm.append(
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.parameters
                    }
                )

        if req.agentFunctions:
            for task in req.agentFunctions:
                schema = SchemaBuilder.build(task.name, task.parameters)
                tm.append(
                    {
                        "name": task.name,
                        "description": task.description,
                        "input_schema": schema
                    }
                )

        if tm:
            params["tools"] = tm

        if req.toolChoice:
            tc = req.toolChoice
            if tc.type == "auto":
                params["tool_choice"] = {"type": "auto"}
            elif tc.type == "any":
                params["tool_choice"] = {"type": "any"}
            elif tc.type == "none":
                params["tool_choice"] = {"type": "none"}
            elif tc.type == "tool" and tc.toolName:
                params["tool_choice"] = {
                    "type": "tool",
                    "name": tc.toolName
                }

    def set_system_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list):
        params["system"] = req.prompt.system

    def set_messages_user_entry(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        content = []
        for ue in me.entries:
            if isinstance(ue, TextPart):
                content.append({"type": "text", "text": ue.text})
            elif isinstance(ue, ImagePart):
                content.append({"type": "image",
                                "source": {"type": "base64", "media_type": ue.mimeType, "data": ue.contentBase64}})
        if content:
            messages.append({"role": "user", "content": content})

    def set_messages_assistant_response_tool_calls(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        messages.append({"role": "assistant", "content": [
            {
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.args,
            } for tc in me.response.tools
        ]})

    def set_messages_assistant_response_content_output(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        parts: list = []
        for _i, part in enumerate(me.response.parts):
            if isinstance(part, TextPart):
                parts.append({
                    "type": "text",
                    "text": part.text
                })
            else:
                ... # Anthropic doesn't support image part
        if parts:
            messages.append({"role": "assistant", "content": parts})


    def set_messages_tool_results(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        messages.append({"role": "user",
                              "content": [
                                  {
                                      "type": "tool_result",
                                      "tool_use_id": tr.id,
                                      "content": json.dumps(tr.result),
                                      **({"is_error": True} if tr.isError else {})
                                  }  for tr in me.responses
                              ]})

    def set_user_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list):
        messages = super().set_user_prompt(req, params, messages)
        params["messages"] = messages

    def set_response_flags(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]):
        reason = response.get("stop_reason")
        if reason == "max_tokens":
            llm_response.did_succeed = False
            llm_response.isMaxTokens = True
            llm_response.failure_reason = "Max tokens exceeded"
        elif reason == "refusal":
            llm_response.did_succeed = False
            llm_response.isFiltered = True
            llm_response.failure_reason = "The model refused to respond (stop_reason=refusal)"
        elif reason == "pause_turn":
            llm_response.did_succeed = False
            llm_response.failure_reason = "The model paused a long-running turn (stop_reason=pause_turn); continuation is not supported"
        else:
            llm_response.did_succeed = True

    def set_token_counts(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]):
        usage = response.get("usage") or {}
        llm_response.inputTextTokens = (usage.get("input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
        llm_response.outputTextTokens = usage.get("output_tokens") or 0

    def set_assistant_vendor(self, llm_response: LlmResponseModel, tool_calls: ToolCalls, content: ContentOutput, response: dict[str, JsonValue]):
        res_content = response.get("content", [])
        for tc in res_content:
            if tc.get("type") == "tool_use":
                tool_calls.tools.append(ToolCall(id=tc.get("id"),
                                                 name=tc.get("name"),
                                                 args=tc.get("input")))
            elif tc.get("type") == "text":
                content.parts.append(TextPart(text=tc.get("text")))
