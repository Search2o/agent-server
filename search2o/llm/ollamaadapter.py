# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

import json
import uuid
from typing import Any

from pydantic import JsonValue

from search2o.common.exceptions import LlmError
from search2o.llm.openaiadapter import OpenaiAdapter
from search2o.llm.schemabuilder import SchemaBuilder
from search2o.models.prompt import AssistantResponse, ContentOutput, LlmRequestModel, LlmResponseModel, TextPart, \
    ToolCall, ToolCalls


class OllamaAdapter(OpenaiAdapter):
    def name(self) -> str:
        return "ollama"

    def description(self) -> str:
        return "Adapter for Ollama's OpenAI compatible responses API"

    @staticmethod
    def forced_tools(req: LlmRequestModel) -> dict[str, dict[str, Any]]:
        tc = req.toolChoice
        if not tc or tc.type not in ("any", "tool"):
            return {}
        tools: dict[str, dict[str, Any]] = {}
        for tool in req.mcpTools:
            tools[tool.name] = {**tool.parameters, "description": tool.description}
        for task in req.agentFunctions:
            tools[task.name] = {**SchemaBuilder.build(task.name, task.parameters), "description": task.description}
        if tc.type == "tool":
            tools = {k: v for k, v in tools.items() if k == tc.toolName}
        return tools

    def set_tools(self, req: LlmRequestModel, params: dict[str, Any]) -> None:
        forced = self.forced_tools(req)
        if forced:
            params["text"] = {"format": {"type": "json_schema", "name": "tool_calls", "strict": True, "schema": {
                "type": "object",
                "properties": forced,
                "required": list(forced) if len(forced) == 1 else [],
                "additionalProperties": False
            }}}
            lines = [("Respond only with a JSON object that calls one or more of these functions. "
                      "Each key is a function name and its value is an object holding that function's arguments.")]
            for name, schema in forced.items():
                lines.append(f"- {name}: {schema['description']} Arguments: {json.dumps(schema.get('properties', {}))}")
            params["instructions"] = "\n".join(lines)
        elif not (req.toolChoice and req.toolChoice.type == "none"):
            super().set_tools(req, params)
            params.pop("tool_choice", None)

    def process_response(self, req: LlmRequestModel, response: dict[str, JsonValue]) -> LlmResponseModel:
        llm_response = super().process_response(req, response)
        forced = self.forced_tools(req)
        asst = llm_response.assistant
        if asst and isinstance(asst.response, ContentOutput) and not any(
                not isinstance(part, TextPart) or part.text for part in asst.response.parts):
            raise LlmError("LLM returned an empty response")
        if forced and asst and isinstance(asst.response, ContentOutput):
            text = "".join(part.text for part in asst.response.parts if isinstance(part, TextPart))
            try:
                calls = json.loads(text)
            except json.JSONDecodeError:
                calls = None
            tools = [ToolCall(id=f"call_{uuid.uuid4().hex}", name=name, args=json.dumps(args), status="completed")
                     for name, args in calls.items() if name in forced and isinstance(args, dict)] if isinstance(calls, dict) else []
            if not tools:
                raise LlmError("LLM did not return a function call")
            llm_response.assistant = AssistantResponse(response=ToolCalls(tools=tools))
        return llm_response
