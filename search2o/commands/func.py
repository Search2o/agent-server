# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations


from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, AskException, CommandInvocation
from search2o.execution.statenodes import FuncCommandNode


class FuncCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, replay_index = inv.frame, inv.command, inv.command_ns, inv.replay_index
        node = executor.get_node(replay_index, FuncCommandNode)
        if node:
            function_name = node.name
            fargs = node.args
            replay_index += 1
        else:
            function_name = executor.param(function, command, command_ns, AgentWords.name, ExpectedType.strt)
            fargs = executor.param(function, command, command_ns, AgentWords.args, ExpectedType.dictstrt)
        return await self.call_function(executor, inv, function_name, fargs, replay_index)

    @staticmethod
    async def call_function(executor: AgentExecutor, inv: CommandInvocation, function_name: str,
                            fargs: dict[str, JsonValue] | None, replay_index: int) -> JsonValue:
        executor.stream_iter.trace(lambda: f"Calling function {function_name!r} with args {fargs if fargs else {}}",
                                   TraceType.input, inv.path)
        try:
            ret = await executor.exec_function(function_name, fargs, replay_index)
            executor.stream_iter.trace(lambda: f"Function {function_name!r} returned {str(ret)[:500]}",
                                       TraceType.output, inv.path)
            return ret
        except AskException as e:
            e.append(FuncCommandNode(name=function_name, args=fargs if fargs else {}))
            raise
