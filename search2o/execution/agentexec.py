# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

from search2o.common.exceptions import ShowMessage
from search2o.models.agentexecmodel import AgentExecModel
from search2o.models.schemaobjects import AgentType


class AgentExec:
    def __init__(self, agent_name: str, agent_title: str, agent_version: int, agent_definition: AgentType,
                 max_time: int | None, max_cost: float | None, secrets_used: list[str] | None = None,
                 last_changed: int = 0):
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

    @classmethod
    def create_for_draft(cls, agent_name: str, agent_title: str, agent_definition: AgentType,
                         max_time: int | None, max_cost: float | None,
                         secrets_used: list[str] | None = None) -> AgentExec:
        # Never added to the cache
        return cls(agent_name, agent_title, 0, agent_definition, max_time, max_cost, secrets_used)
