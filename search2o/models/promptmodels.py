# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

from enum import StrEnum, auto
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .configtypes import PromptText


class PromptScope(StrEnum):
    conversation = auto()
    agent = auto()
    local = auto()


class AgentPromptModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: Annotated[PromptText | None, Field(default=None, title="System prompt", description="The system prompt. It must evaluate to text.")]
    user: Annotated[PromptText | None, Field(default=None, title="User prompt", description="The user prompt. Evaluated at each LLM call that uses this prompt. It must evaluate to text, a content part ({contentType: text|image}), or a list of them.")]
    scope: Annotated[PromptScope, Field(default=PromptScope.conversation, title="Scope", description="How long the prompt's history is kept.")]
    doc: Annotated[str | None, Field(default=None, title="Documentation", description="What the prompt is for. Shown to draft help in place of the prompt's text.")]

    @model_validator(mode="after")
    def require_text(self) -> Self:
        if not self.system and not self.user:
            raise ValueError("A prompt needs a system prompt, a user prompt, or both.")
        return self
