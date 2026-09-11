# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import copy
from typing import Any

from pydantic import JsonValue

from search2o.common.exceptions import LlmError
from search2o.llm.basellmadapter import BaseLlmAdapter
from search2o.llm.schemabuilder import SchemaBuilder
from search2o.models.prompt import ToolCall, ContentOutput, TextPart, ToolCalls, \
    PromptElement, ImagePart, LlmResponseModel, LlmRequestModel


class GeminiAdapter(BaseLlmAdapter):
    def name(self) -> str:
        return "gemini"

    def description(self) -> str:
        return "Adapter for Google Gemini or any vendor that is compatible with it"

    def set_model(self, req: LlmRequestModel, params: dict[str, Any]):
        ...

    def set_max_tokens(self, req: LlmRequestModel, params: dict[str, Any]):
        if "generationConfig" not in params:
            params["generationConfig"] = {}
        params["generationConfig"]["maxOutputTokens"] = req.maxTokens

    def set_tools(self, req: LlmRequestModel, params: dict[str, Any]) -> None:
        tools = []

        for tool in req.vendorTools:
            tools.append(tool)

        # MCP + agent-function tools go together inside a single functionDeclarations entry.
        function_declarations = []

        if req.mcpTools:
            for tool in req.mcpTools:
                tp_copy = copy.deepcopy(tool.parameters)
                schema = SchemaBuilder.strip_gemini_dev_forbidden(tp_copy)
                function_declarations.append(
                    {
                        "name": tool.name,
                        "description": tool.description + (".  Does not take any parameters." if not tool.parameters.get("properties") else ""),
                        "parameters": schema
                    }
                )

        if req.agentFunctions:
            for task in req.agentFunctions:
                schema = SchemaBuilder.build(task.name, task.parameters)
                schema = SchemaBuilder.strip_gemini_dev_forbidden(schema)
                function_declarations.append(
                    {
                        "name": task.name,
                        "description": task.description + (".  Does not take any parameters." if not task.parameters else ""),
                        "parameters": schema
                    }
                )

        if function_declarations:
            tools.append({"functionDeclarations": function_declarations})

        if tools:
            params["tools"] = tools

        if req.toolChoice:
            tc = req.toolChoice
            if tc.type == "auto":
                params["toolConfig"] = { "functionCallingConfig": {"mode": "AUTO"} }
            elif tc.type == "any":
                params["toolConfig"] = { "functionCallingConfig": {"mode": "ANY"} }
            elif tc.type == "none":
                params["toolConfig"] = { "functionCallingConfig": {"mode": "NONE"} }
            elif tc.type == "tool" and tc.toolName:
                params["toolConfig"] = {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [tc.toolName]
                    }
                }

    def set_system_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list):
        params["systemInstruction"] = {
            "role": "user",
            "parts": [{
                "text": req.prompt.system
            }]
        }

    def set_user_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list):
        super().set_user_prompt(req, params, messages)
        params["contents"] = messages

    def set_messages_user_entry(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        parts = []
        for ue in me.entries:
            if isinstance(ue, TextPart):
                parts.append({"text": ue.text})
            elif isinstance(ue, ImagePart):
                parts.append({"inlineData": {"data": ue.contentBase64, "mimeType": ue.mimeType}})
        if parts:
            messages.append({"role": "user", "parts": parts})

    def set_messages_assistant_response_tool_calls(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        calls = []
        for tc in me.response.tools:
            part =  {
                "functionCall": {
                    "name": tc.name,
                    "args": tc.args
                }
            }
            if tc.additionalFields and "thoughtSignature" in tc.additionalFields:
                part["thoughtSignature"] = tc.additionalFields["thoughtSignature"]
            calls.append(part)
        messages.append({
            "role": "model",
            "parts": calls
        })

    def set_messages_assistant_response_content_output(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        parts = []
        for _i, part in enumerate(me.response.parts):
            p = None
            if isinstance(part, TextPart):
                p = { "text": part.text }
                if part.additionalFields and "thoughtSignature" in part.additionalFields:
                    p["thoughtSignature"] = part.additionalFields["thoughtSignature"]
            elif isinstance(part, ImagePart):
                p = {
                    "inlineData": {
                        "data": part.contentBase64,
                        "mimeType": part.mimeType,
                    }
                }
            if p:
                parts.append(p)
        if parts:
            messages.append({"role": "model",
                                  "parts": parts
                                  })


    def set_messages_tool_results(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        messages.append({ "role": "user",
                               "parts": [
                                   {
                                       "functionResponse": {
                                           "name": tr.name,
                                           "response": tr.result
                                       }
                                   } for tr in me.responses
                               ]
                               })

    def set_response_flags(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]):
        ca = response.get("candidates")
        if ca:
            cand = ca[0]
            reason = cand.get("finishReason")
            if reason == "MAX_TOKENS":
                llm_response.isMaxTokens = True
                llm_response.failure_reason = "Max tokens exceeded"
            elif reason in {"MALFORMED_FUNCTION_CALL", "SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                if reason == "MALFORMED_FUNCTION_CALL":
                    llm_response.should_retry = True
                llm_response.isFiltered = True
                llm_response.failure_reason = f"Response blocked by Gemini (finishReason={reason})"
            else:
                llm_response.did_succeed = True
        else:
            block_reason = (response.get("promptFeedback") or {}).get("blockReason")
            llm_response.failure_reason = f"Gemini returned no candidates (blockReason={block_reason})"

    def set_token_counts(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]):
        usage = response.get("usageMetadata")
        if usage:
            prompt_total = (usage.get("promptTokenCount") or 0) + (usage.get("toolUsePromptTokenCount") or 0)
            candidates_total = (usage.get("candidatesTokenCount") or 0) + (usage.get("thoughtsTokenCount") or 0)

            prompt_details: list[dict[str, Any]] = usage.get("promptTokensDetails") or []
            candidate_details: list[dict[str, Any]] = usage.get("candidatesTokensDetails") or []

            # ---------- INPUT SIDE ----------
            if prompt_details:
                # We *do* have per-modality info for the prompt
                text_in_from_prompt = sum(
                    (d.get("tokenCount") or 0) for d in prompt_details if d.get("modality") == "TEXT"
                )
                image_in = sum(
                    (d.get("tokenCount") or 0) for d in prompt_details if d.get("modality") == "IMAGE"
                )
                # toolUsePromptTokenCount is effectively extra text
                text_in = text_in_from_prompt + (usage.get("toolUsePromptTokenCount") or 0)
            else:
                # No details → fall back to the previous behavior: everything is text
                text_in = prompt_total
                image_in = 0

            # ---------- OUTPUT SIDE ----------
            candidates_token_count = usage.get("candidatesTokenCount") or 0
            thoughts_token_count = usage.get("thoughtsTokenCount") or 0

            if candidate_details:
                # We have per-modality info for candidates
                image_out_from_candidates = sum(
                    (d.get("tokenCount") or 0) for d in candidate_details if d.get("modality") == "IMAGE"
                )
                non_text_from_candidates = sum(
                    (d.get("tokenCount") or 0)
                    for d in candidate_details
                    if d.get("modality") != "TEXT"
                )
                text_from_candidates = candidates_token_count - non_text_from_candidates

                image_out = image_out_from_candidates
                # thoughtsTokenCount is extra text output
                text_out = text_from_candidates + thoughts_token_count
            else:
                # No details → fall back to the previous behavior: everything is text
                image_out = 0
                text_out = candidates_total

            llm_response.inputTextTokens = text_in
            llm_response.outputTextTokens = text_out
            llm_response.inputImageTokens = image_in
            llm_response.outputImageTokens = image_out

    def set_assistant_vendor(self, llm_response: LlmResponseModel, tool_calls: ToolCalls, content: ContentOutput, response: dict[str, JsonValue]):
        try:
            cand: dict = response["candidates"][0]
            parts: list[dict] = (cand.get("content") or {}).get("parts") or []
        except (KeyError, IndexError, TypeError) as ex:
            raise LlmError(f"Unexpected response from Gemini LLM: {ex!r}")
        for tc in parts:
            if "functionCall" in tc:
                fc: dict = tc["functionCall"]
                name = fc.get("name")
                tool_call = ToolCall(
                    id=name,
                    name=name,
                    args=fc.get("args")
                )
                signature = tc.get("thoughtSignature")
                if signature:
                    tool_call.additionalFields = {
                        "thoughtSignature": signature
                    }
                tool_calls.tools.append(tool_call)
            elif "text" in tc:
                part = TextPart(text=tc["text"])
                signature = tc.get("thoughtSignature")
                if signature:
                    part.additionalFields = {
                        "thoughtSignature": signature
                    }
                content.parts.append(part)
            elif "inlineData" in tc:
                data = tc["inlineData"]
                part = ImagePart(contentBase64=data.get("data"), mimeType=data.get("mimeType"))
                signature = tc.get("thoughtSignature")
                if signature:
                    part.additionalFields = {
                        "thoughtSignature": signature
                    }
                content.parts.append(part)
