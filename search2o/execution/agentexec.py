# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

import json
import types
from typing import TYPE_CHECKING

from pydantic import BaseModel

from search2o.common.exceptions import ShowMessage, error_message
from search2o.models.agentexecmodel import AgentExecModel
from search2o.models.promptmodels import PromptScope
from search2o.models.schemaobjects import AgentType

if TYPE_CHECKING:
    from starlette.requests import Request
    from search2o.execution.runtime import RuntimeState


def dollars(amount: float) -> str:
    text = f"{amount:.6f}".rstrip("0")
    whole, cents = text.split(".")
    return f"${whole}.{cents.ljust(2, '0')}"


class ExecPrompt(BaseModel):
    scope: PromptScope
    system: str | None = None
    user: str | None = None


class AgentExec:
    def __init__(self, agent_name: str, agent_title: str, agent_version: int, agent_definition: AgentType,
                 max_time: int | None, max_cost: float | None, secrets_used: list[str] | None = None,
                 last_changed: int = 0, agent_prompts: dict[str, dict] | None = None,
                 const: dict | None = None):
        if not max_time or not max_cost:
            raise ShowMessage(f"Search2o did not send the run limits of agent {agent_name!r}, so it cannot be run. "
                              f"Search2o Cloud and this agent server may be on different releases.")
        self.agent_name = agent_name
        self.max_time = max_time
        self.max_cost = max_cost
        self.last_changed = last_changed
        self.secrets_used = secrets_used or []
        self.agent_title = agent_title
        self.agent_version = agent_version
        self.agent_definition = AgentExecModel.model_validate_json(agent_definition)
        self.prompts = {name: ExecPrompt.model_validate(p) for name, p in (agent_prompts or {}).items()}
        self.const = const or {}
        self.compiled: dict[str, types.CodeType] = {}

    @classmethod
    def create_for_draft(cls, agent_name: str, agent_title: str, agent_definition: AgentType,
                         max_time: int | None, max_cost: float | None,
                         secrets_used: list[str] | None = None,
                         agent_prompts: dict[str, dict] | None = None,
                         const: dict | None = None) -> AgentExec:
        # Never added to the cache
        return cls(agent_name, agent_title, 0, agent_definition, max_time, max_cost, secrets_used,
                   agent_prompts=agent_prompts, const=const)

    @classmethod
    async def decrypt_const(cls, request: Request, runtime: RuntimeState, agent_name: str,
                            encrypted: str | None) -> dict:
        if not encrypted:
            return {}
        from search2o.execution.encryptor import Encryptor
        try:
            value = json.loads(await Encryptor.decrypt(request, runtime, encrypted))
        except ShowMessage:
            raise
        except Exception as e:
            raise ShowMessage(f"The const of agent {agent_name!r} could not be decrypted and read as JSON: "
                              f"{error_message(e)}")
        if not isinstance(value, dict):
            raise ShowMessage(f"The const of agent {agent_name!r} must be a JSON object.")
        return value
