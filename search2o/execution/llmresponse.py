# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from dataclasses import dataclass

from pydantic import JsonValue

from search2o.common.toolcallmethods import ToolCallMethods
from search2o.models.prompt import ToolCalls, ContentOutput, TextPart, LlmResponseModel


@dataclass
class LlmTokens:
    text: int = 0
    image: int = 0

@dataclass
class LlmResult:
    profile: str
    model: str
    duration: int
    tool_call: bool
    input_tokens: LlmTokens
    output_tokens: LlmTokens


class LlmResponse:
    def __init__(self, response: LlmResponseModel):
        self.response = response

    def get_text(self) -> str:
        li: list[str] = []
        if self.response.assistant:
            if isinstance(self.response.assistant.response, ContentOutput):
                for part in self.response.assistant.response.parts:
                    if isinstance(part, TextPart):
                        li.append(part.text)
        return "\n".join(li)

    def get_tool_calls(self) -> dict[str, JsonValue]:
        d = {}
        if self.response.assistant:
            if isinstance(self.response.assistant.response, ToolCalls):
                for t in self.response.assistant.response.tools:
                    _, fn = ToolCallMethods.retrieve_name(t.name)
                    d[fn] = ToolCallMethods.get_tool_args(t.args)
        return d






