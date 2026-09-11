# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import json
from abc import abstractmethod
from collections.abc import Mapping
from typing import Any

from pydantic import JsonValue

from search2o.common.exceptions import LlmError
from search2o.llm.llmadapter import LlmAdapter
from search2o.models.prompt import ToolCalls, ContentOutput, AssistantResponse, UserEntry, ToolResults, PromptElement, \
    LlmRequestModel, LlmResponseModel


class BaseLlmAdapter(LlmAdapter):
    def process_request(self, req: LlmRequestModel) -> dict[str, JsonValue]:
        params: dict[str, Any] = {}
        messages: list = []
        self.set_model(req, params)
        self.set_max_tokens(req, params)
        self.set_tools(req, params)
        self.set_system_prompt(req, params, messages)
        self.set_user_prompt(req, params, messages)
        params = self._deep_merge(params, req.additionalParams)
        return params

    def process_response(self, req: LlmRequestModel, response: dict[str, JsonValue]) -> LlmResponseModel:
        llm_response: LlmResponseModel = LlmResponseModel()
        self.set_response_flags(llm_response, response)
        self.set_token_counts(llm_response, response)
        if llm_response.did_succeed:
            tool_calls = ToolCalls()
            content = ContentOutput()
            self.set_assistant_vendor(llm_response, tool_calls, content, response)
            if tool_calls.tools:
                llm_response.assistant = AssistantResponse(response=tool_calls)
            elif content.parts:
                llm_response.assistant = AssistantResponse(response=content)
            else:
                raise LlmError("LLM did not set a response")
        return llm_response

    def get_error(self, req: LlmRequestModel, response: dict[str, JsonValue]) -> str:
        error = response.get("error")
        if error:
            if isinstance(error, dict):
                return json.dumps(error, indent=2)
            else:
                return str(error)
        else:
            return f"LLM {self.name()} returned an error without a valid error message"

    @abstractmethod
    def set_model(self, req: LlmRequestModel, params: dict[str, Any]):
        ...

    @abstractmethod
    def set_max_tokens(self, req: LlmRequestModel, params: dict[str, Any]):
        ...

    @abstractmethod
    def set_tools(self, req: LlmRequestModel, params: dict[str, Any]):
        ...

    @abstractmethod
    def set_system_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list):
        ...

    def set_user_prompt(self, req: LlmRequestModel, params: dict[str, Any], messages: list) -> list:
        for me in req.prompt.elements:
            if isinstance(me, UserEntry):
                self.set_messages_user_entry(req, params,me, messages)
            elif isinstance(me, AssistantResponse):
                if isinstance(me.response, ToolCalls):
                    self.set_messages_assistant_response_tool_calls(req, params,me, messages)
                elif isinstance(me.response, ContentOutput):
                    self.set_messages_assistant_response_content_output(req, params, me, messages)
            elif isinstance(me, ToolResults):
                self.set_messages_tool_results(req, params, me, messages)
        return messages

    @abstractmethod
    def set_messages_tool_results(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        ...

    @abstractmethod
    def set_messages_assistant_response_tool_calls(self, req: LlmRequestModel, params: dict[str, Any], me: AssistantResponse, messages: list):
        ...

    @abstractmethod
    def set_messages_assistant_response_content_output(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        ...

    @abstractmethod
    def set_messages_user_entry(self, req: LlmRequestModel, params: dict[str, Any], me: PromptElement, messages: list):
        ...

    @abstractmethod
    def set_response_flags(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]):
        ...

    @abstractmethod
    def set_token_counts(self, llm_response: LlmResponseModel, response: dict[str, JsonValue]):
        ...

    @abstractmethod
    def set_assistant_vendor(self, llm_response: LlmResponseModel, tool_calls: ToolCalls, content: ContentOutput, response: dict[str, JsonValue]):
        ...

    @classmethod
    def _deep_merge(cls, left: Mapping[str, Any], right: Mapping[str, Any]):
        out: dict[str, Any] = dict(left)

        for k, rv in right.items():
            if k not in out:
                out[k] = rv
                continue

            lv = out[k]

            if isinstance(lv, Mapping) and isinstance(rv, Mapping):
                out[k] = cls._deep_merge(lv, rv)
            elif isinstance(lv, list) and isinstance(rv, list):
                out[k] = [*lv, *rv]
            else:
                out[k] = rv  # rhs wins

        return out
