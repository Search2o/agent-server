# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

from types import TracebackType
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr, TypeAdapter, ValidationError

from search2o.common.exceptions import ShowMessage
from search2o.common.jsonvalidation import JsonValidator
from search2o.models.schemaobjects import ContentPartApi, ImagePartApi

from search2o.models.prompt import PromptModel, UserEntry, AssistantResponse, ToolResults, \
    PromptElement, TextPart, ImagePart


_CONTENT_PART = TypeAdapter(ContentPartApi)


def user_parts(val: Any, where: str) -> list[TextPart | ImagePart]:
    items = val if isinstance(val, list) else [val]
    parts: list[TextPart | ImagePart] = []
    for i, item in enumerate(items, 1):
        at = f"{where} item {i}" if isinstance(val, list) else where
        if isinstance(item, str):
            if item:
                parts.append(TextPart(text=item))
            continue
        if not isinstance(item, dict):
            raise ShowMessage(f"{at} must be text, a content part or a list of them, not {type(item).__name__}.")
        if item.get("contentType") not in ("text", "image"):
            raise ShowMessage(f"{at} must be a content part with a contentType of 'text' or 'image', "
                              f"not {item.get('contentType')!r}: {str(item)[:100]}")
        try:
            part = _CONTENT_PART.validate_python(item)
        except ValidationError as e:
            raise ShowMessage(f"{at} is not a valid content part: {JsonValidator.error_text(e, item)}")
        if isinstance(part, ImagePartApi):
            if not part.mimeType:
                raise ShowMessage(f"{at} is an image part without a mimeType.")
            parts.append(ImagePart(contentBase64=part.data, mimeType=part.mimeType))
        elif part.text:
            parts.append(TextPart(text=part.text))
    return parts


class PromptHelper:
    def __init__(self, prompts: Prompts, name: str) -> None:
        self._prompts = prompts
        self._name = name
        self._acquired = False
        self.prompt: PromptModel | None = None

    def __enter__(self) -> PromptHelper:
        if self._name in self._prompts._acquired:
            raise ShowMessage(f"The prompt {self._name!r} is already in use by another llm command that has not "
                              f"finished: one in another parallel branch, or the llm command that called this tool. "
                              f"llm commands running at the same time must use different prompts.")
        self._prompts._acquired.add(self._name)
        self.prompt = self._prompts.get_prompt(self._name)
        self._acquired = True
        return self

    def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
    ) -> Literal[False]:
        if self._acquired:
            self._acquired = False
            self._prompts._acquired.discard(self._name)
        self.prompt = None
        return False

    def set_system(self, s: str) -> None:
        self.prompt.system = s

    def get_last_user_entry(self):
        elements: list[PromptElement] = self.prompt.elements
        if elements:
            last_agent_response = -1
            for i in range(len(elements) -1, -1, -1):
                ele = elements[i]
                if isinstance(ele, AssistantResponse):
                    last_agent_response = i
                    break
            if last_agent_response > -1:
                for ele in elements[last_agent_response+1:]:
                    if isinstance(ele, UserEntry):
                        return ele
            else: # No asst response
                for ele in elements:
                    if isinstance(ele, UserEntry):
                        return ele
        ue = UserEntry()
        elements.append(ue)
        return ue


    def add_user(self, val: str | list[TextPart | ImagePart]):
        parts = [TextPart(text=val)] if isinstance(val, str) else val
        if parts:
            self.get_last_user_entry().entries.extend(parts)

    def add_assistant(self, assistant: AssistantResponse) -> None:
        self.prompt.elements.append(assistant)

    def add_tools(self, tools: ToolResults) -> None:
        self.prompt.elements.append(tools)



class Prompts(BaseModel):
    prompts: dict[str, "PromptModel"] = Field(default_factory=dict)
    _acquired: set[str] = PrivateAttr(default_factory=set)

    def get_prompt(self, name: str) -> PromptModel:
        prompt = self.prompts.get(name)
        if not prompt:
            prompt = PromptModel(name=name)
            self.prompts[name] = prompt
        return prompt


