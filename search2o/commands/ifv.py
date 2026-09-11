# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations


from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, AskException, CommandInvocation
from search2o.execution.statenodes import IfCommandNode


class IfCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, path, replay_index = inv.frame, inv.command, inv.command_ns, inv.path, inv.replay_index
        node = executor.get_node(replay_index, IfCommandNode)
        if node is not None:
            cond = node.condValue
            replay_index += 1
            executor.stream_iter.trace(lambda: f"If condition was already evaluated to {cond}", TraceType.flow, inv.path)
        else:
            cond = executor.param(function, command, command_ns, AgentWords.condition)
            executor.stream_iter.trace(lambda: f"If condition evaluated to {cond}", TraceType.flow, inv.path)
        try:
            if cond:
                await executor.exec_commands_no_breaks(function, command.command_list(AgentWords.then), path, replay_index)
            else:
                await executor.exec_commands_no_breaks(function, command.command_list(AgentWords.else_s), path, replay_index)
        except AskException as e:
            e.append(IfCommandNode(condValue=cond))
            raise
