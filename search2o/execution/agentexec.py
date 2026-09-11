# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from search2o.models.agentexecmodel import AgentExecModel
from search2o.models.schemaobjects import AgentType


class AgentExec:
    def __init__(self, agent_name: str, agent_title: str, agent_version: int, agent_definition: AgentType):
        self.agent_name = agent_name
        self.agent_title = agent_title
        self.agent_version = agent_version
        self.agent_definition = AgentExecModel.model_validate_json(agent_definition)

    @classmethod
    def create_for_draft(cls, agent_name: str, agent_title: str, agent_definition: AgentType) -> AgentExec:
        # Never added to the cache
        return cls(agent_name, agent_title, 0, agent_definition)
