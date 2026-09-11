# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import json
from typing import Any

from pydantic import BaseModel, JsonValue, Field, TypeAdapter, ValidationError

from search2o.common.exceptions import ShowMessage
from search2o.common.htmlchecker import HtmlChecker
from search2o.common.mynamespace import ConvNamespace, ConvNamespaceField, AgentNamespaceField
from search2o.execution.llmresponse import LlmResponse
from search2o.execution.prompts import Prompts
from search2o.execution.statenodes import NodeUnion
from search2o.models.prompt import TextPart, ContentOutput, ImagePart, ToolCalls
from search2o.models.schemaobjects import TextPartApi, HtmlPartApi, ImagePartApi, ContentPartApi, \
    CommandName


_CONTENT_PART = TypeAdapter(ContentPartApi)


class AgentOutput(BaseModel):
    agentName: str = Field(default="unknown")
    parts: list[ContentPartApi] = Field(default_factory=list)

    @staticmethod
    def _add_str(parts: list[ContentPartApi], text: str):
        parts.append(TextPartApi(text=text))

    @staticmethod
    def _add_html(parts: list[ContentPartApi], html: str):
        parts.append(HtmlPartApi(text=html))

    @staticmethod
    def _add_image(parts: list[ContentPartApi], data: str, mt: str):
        if not mt:
            raise ShowMessage("mimeType must be specified for image output")
        parts.append(ImagePartApi(text=data, mimeType=mt))


    def _add_llm(self, parts: list[ContentPartApi], co: ContentOutput | ToolCalls):
        if isinstance(co, ContentOutput):
            for part in co.parts:
                if isinstance(part, TextPart):
                    if part.text and HtmlChecker.is_html(part.text):
                        self._add_html(parts, part.text)
                    else:
                        self._add_str(parts, part.text)
                elif isinstance(part, ImagePart):
                    self._add_image(parts, part.contentBase64, part.mimeType)
        elif isinstance(co, ToolCalls):
            for tc in co.tools:
                self._add_str(parts, tc.model_dump_json(indent=2))


    def _add_dict(self, parts: list[ContentPartApi], d: dict[str, JsonValue]):
        try:
            part = _CONTENT_PART.validate_python(d)
        except ValidationError:
            raise ShowMessage(f"A part of the '{CommandName.output}' command must have a contentType of "
                              f"'text', 'html' or 'image' and the content in 'text'. "
                              f"Got: {json.dumps(d, default=str)}")
        if isinstance(part, ImagePartApi) and not part.mimeType:
            raise ShowMessage(f"An image part of the '{CommandName.output}' command must have a mimeType.")
        parts.append(part)

    def _add_list(self, parts: list[ContentPartApi], values: list[JsonValue]):
        for d in values:
            if isinstance(d, dict):
                self._add_dict(parts, d)
            elif isinstance(d, str):
                self._add_str(parts, d)


    def add(self, val: str | dict | list | LlmResponse) -> list[ContentPartApi]:
        parts: list[ContentPartApi] = []
        if isinstance(val, LlmResponse): # This needs to be there before dict
            if val.response.assistant:
                self._add_llm(parts, val.response.assistant.response)
        elif isinstance(val, dict):
            self._add_dict(parts, val)
        elif isinstance(val, list):
            self._add_list(parts, val)
        elif isinstance(val, str):
            self._add_str(parts, val)
        else:
            self._add_str(parts, str(val))
        self.parts.extend(parts)
        return parts

    def is_set(self) -> bool:
        return bool(self.parts)

    @staticmethod
    def is_valid_type(obj: Any) -> bool:
        return isinstance(obj, (str | ContentOutput))


class AgentRun(BaseModel):
    agentName: str # agentName is here and in AgentOutput, but the purpose is different (AgentOutput is for the UI)
    agentVersion: int
    inputs: dict[str, JsonValue]
    output: AgentOutput = Field(default_factory=AgentOutput)
    callstack: list[NodeUnion] = []
    execAt: int


class ConversationState(BaseModel):
    runs: list[AgentRun] = Field(default_factory=list)
    prompts: Prompts = Field(default_factory=Prompts)

    conversationVars: ConvNamespaceField = Field(
        default_factory=ConvNamespace
    )

    agentVars: dict[str, AgentNamespaceField] = Field(
        default_factory=dict
    )


