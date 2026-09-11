# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from types import TracebackType
from typing import Literal

from pydantic import BaseModel, Field, PrivateAttr

from search2o.common.exceptions import ShowMessage

from search2o.common.enums import AgentWords
from search2o.models.prompt import PromptModel, UserEntry, AssistantResponse, ToolResults, \
    PromptElement, TextPart, ImagePart


class PromptHelper:
    def __init__(self, prompts: Prompts, name: str) -> None:
        self._prompts = prompts
        self._name = name
        self._acquired = False
        self.prompt: PromptModel | None = None

    def __enter__(self) -> PromptHelper:
        if self._name in self._prompts._acquired:
            raise ShowMessage(f"The prompt {self._name!r} is already in use by another command. "
                              f"A nested agent or a tool call must use a different prompt.")
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


    def add_user(self, val: str | dict | list):
        if val:
            if isinstance(val, str):
                self.get_last_user_entry().entries.append(TextPart(text=val))
            elif isinstance(val, dict):
                t = val.get("contentType")
                if t == "text":
                    self.add_user(val.get("text"))
                elif t == "image":
                    data = val.get("contentBase64")
                    mt = val.get("mimeType")
                    if data and mt:
                        self.get_last_user_entry().entries.append(ImagePart(contentBase64=data, mimeType=mt))
            elif isinstance(val, list):
                for v in val:
                    self.add_user(v)

    def add_assistant(self, assistant: AssistantResponse) -> None:
        self.prompt.elements.append(assistant)

    def add_tools(self, tools: ToolResults) -> None:
        self.prompt.elements.append(tools)



class Prompts(BaseModel):
    prompts: dict[str, "PromptModel"] = Field(default_factory=lambda: Prompts._default_prompts())
    _acquired: set[str] = PrivateAttr(default_factory=set)

    @classmethod
    def _default_prompts(cls) -> dict[str, PromptModel]:
        name = AgentWords.default.name
        return {name: PromptModel(name=name)}

    def get_prompt(self, name: str) -> PromptModel:
        if name:
            prompt = self.prompts.get(name, None)
            if prompt:
                return prompt
            else:
                prompt = PromptModel(name=name)
                self.prompts[name] = prompt
                return prompt
        else:
            prompt = self.prompts[AgentWords.default.name]
            return prompt


