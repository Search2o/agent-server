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


class OpenaiAdapter(BaseLlmAdapter):
    def name(self) -> str:
        return "openai"

    def description(self) -> str:
        return "Adapter for OpenAI ChatGPT responses API or any vendor that is compatible with it"

    def set_model(self, req: LlmRequestModel, params: dict[str, Any]):
        params["model"] = req.model

    def set_max_tokens(self, req: LlmRequestModel, params: dict[str, Any]):
        params["max_output_tokens"] = req.maxTokens

    def set_tools(self, req: LlmRequestModel, params: dict[str, Any]) -> None:
        tm = []

        for tool in req.vendorTools:
            tm.append(tool)

        if req.mcpTools:
            for tool in req.mcpTools:
                tm.append({
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                })

        if req.agentFunctions:
            for task in req.agentFunctions:
                schema = SchemaBuilder.build(task.name, task.parameters)
                tm.append({
                    "type": "function",
                    "name": task.name,
                    "description": task.description,
                    "parameters": schema
                })

        if tm:
            params["tools"] = tm

        if req.toolChoice:
            tc = req.toolChoice
            if tc.type == "auto":
                params["tool_choice"] = "auto"
            elif tc.type == "any":
                params["tool_choice"] = "required"
            elif tc.type == "none":
                params["tool_choice"] = "none"
            elif tc.type == "tool" and tc.toolName:
                params["tool_choice"] = {
                    "type": "function",
                    "name": tc.toolName
                }

    def set_system_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list):
        messages.append({"role": "system",
                              "content": [{
                                  "type": "input_text",
                                  "text": req.prompt.system
                              }]
                              }
                             )

    def set_user_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list):
        super().set_user_prompt(req, params, messages)
        params["input"] = messages

    def set_messages_user_entry(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        content = []
        for ue in me.entries:
            if isinstance(ue, TextPart):
                content.append({"type": "input_text", "text": ue.text})
            elif isinstance(ue, ImagePart):
                content.append({"type": "input_image",
                                "image_url": f"data:{ue.mimeType};base64,{ue.contentBase64}"})
        if content:
            messages.append({"role": "user", "content": content})


    def set_messages_assistant_response_tool_calls(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        for tc in me.response.tools:
            messages.append({
                "type": "function_call",
                "call_id": tc.id,
                "name": tc.name,
                "arguments": tc.args,
            })

    def set_messages_assistant_response_content_output(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        text_parts: list = []
        for part in me.response.parts:
            if isinstance(part, TextPart):
                text_parts.append({"type": "output_text", "text": part.text})
            elif isinstance(part, ImagePart):
                if part.reasoning_openai:
                    messages.append(part.reasoning_openai)
                messages.append({
                    "type": "image_generation_call",
                    "id": part.id_openai,
                })
        if text_parts:
            messages.append({"role": "assistant", "content": text_parts})


    def set_messages_tool_results(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        for tr in me.responses:
            messages.append({
                "type": "function_call_output",
                "call_id": tr.id,
                "output": json.dumps(tr.result),
            })

    def set_response_flags(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]):
        status = response.get("status")
        if status == "incomplete":
            finish_reason = (response.get("incomplete_details") or {}).get("reason")
            if finish_reason == "max_output_tokens":
                llm_response.isMaxTokens = True
                llm_response.failure_reason = "Max tokens exceeded"
            elif finish_reason == "content_filter":
                llm_response.isFiltered = True
                llm_response.failure_reason = "Response blocked by content filter"
            else:
                llm_response.failure_reason = f"LLM response incomplete (reason={finish_reason})"
        elif status in {"failed", "cancelled", "queued", "in_progress"}:
            error = (response.get("error") or {}).get("message")
            llm_response.failure_reason = f"LLM response status was '{status}'" + (f": {error}" if error else "")
        else:
            llm_response.did_succeed = True

    def set_token_counts(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]) -> None:
        usage = response.get("usage")
        if not isinstance(usage, dict):
            return

        llm_response.inputTextTokens = usage.get("input_tokens") or 0
        llm_response.outputTextTokens = usage.get("output_tokens") or 0

        # Future-proofing: only set if present (commonly present for GPT image endpoints/events)
        input_details = usage.get("input_tokens_details")
        if isinstance(input_details, dict):
            llm_response.inputImageTokens = input_details.get("image_tokens") or 0

        output_details = usage.get("output_tokens_details")
        if isinstance(output_details, dict):
            llm_response.outputImageTokens = output_details.get("image_tokens") or 0


    def set_assistant_vendor(self, llm_response: LlmResponseModel, tool_calls: ToolCalls, content: ContentOutput, response: dict[str, JsonValue]):
        output = response.get("output")
        pending_reasoning = None
        for o in (output or []):
            typ = o.get("type")
            if typ == "reasoning":
                pending_reasoning = o
            elif typ == "message":
                t = o.get("content")
                for c in (t or []):
                    if c.get("type") == "output_text":
                        content.parts.append(TextPart(text=c.get("text")))
            elif typ == "image_generation_call":
                image = o.get("result")
                if image:
                    content.parts.append(ImagePart(contentBase64=image,
                                                   mimeType="image/png",
                                                   id_openai=o.get("id"),
                                                   reasoning_openai=pending_reasoning))
                    pending_reasoning = None
            elif typ == "function_call":
                tool_calls.tools.append(ToolCall(
                    id=o.get("call_id"),
                    name=o.get("name"),
                    args=o.get("arguments"),
                    status="completed" # We cheat to make it easier on the client. Ideally, this should be "in_progress" and sent back as "completed"
                ))
