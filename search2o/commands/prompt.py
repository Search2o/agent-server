# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations


from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import ShowMessage
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation
from search2o.execution.prompts import PromptHelper


class PromptCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns = inv.frame, inv.command, inv.command_ns
        name = executor.param(function, command, command_ns, AgentWords.name, ExpectedType.strt)
        profile_name = executor.param(function, command, command_ns, AgentWords.profile, ExpectedType.strt)
        system_value = None
        user_value = None
        if profile_name:
            prompt_profile = executor.runtime.prompts.get(profile_name)
            if not prompt_profile:
                raise ShowMessage(f"Prompt profile {profile_name} not found")
            system_value = prompt_profile.system
            user_value = prompt_profile.user

        system_value_agent = executor.param(function, command, command_ns, AgentWords.system, ExpectedType.strt)
        if system_value_agent:
            system_value = system_value_agent
        user_value_agent = executor.param(function, command, command_ns, AgentWords.user, ExpectedType.anyt)
        if user_value_agent is not None:
            user_value = user_value_agent

        with PromptHelper(executor.prompts, name) as prompt_helper:
            if system_value is not None:
                prompt_helper.set_system(system_value)
            if user_value:
                prompt_helper.add_user(user_value)
            executor.stream_iter.trace(lambda: f"Prompt {name!r}"
                                               + (f" from profile {profile_name!r}" if profile_name else "")
                                               + (f", system = {str(system_value)[:500]!r}" if system_value is not None else "")
                                               + (f", user = {str(user_value)[:500]!r}" if user_value else ""), TraceType.input, inv.path)


