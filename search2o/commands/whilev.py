# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio

from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import ShowMessage
from search2o.execution.agent_executor import AgentExecutor, CommandExec, AskException, CommandInvocation
from search2o.execution.statenodes import WhileCommandNode

class WhileCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, path, replay_index = inv.frame, inv.command, inv.command_ns, inv.path, inv.replay_index
        node = executor.get_node(replay_index, WhileCommandNode)
        yield_after = executor.runtime.validation.yieldLoopsAfter
        maxiter = executor.runtime.validation.maxIterationLoops
        doit = command.command_list(AgentWords.do)

        if node:
            cond = True
            replay_index += 1
            cnt = node.cnt
        else:
            cond = executor.param(function, command, command_ns, AgentWords.condition)
            cnt = 1

        executor.stream_iter.trace(lambda: f"While condition evaluated to {cond}"
                                           + (f", resuming at iteration {cnt}" if node else ""), TraceType.flow, inv.path)
        if doit:
            while cond:
                if cnt % yield_after == 0:
                    await asyncio.sleep(0)
                if cnt > maxiter:
                    raise ShowMessage(f"While loop iterations greater than the max configured: {maxiter}")
                try:
                    res = await executor.exec_command_list(function, doit, path, replay_index)
                except AskException as e:
                    e.append(WhileCommandNode(cnt=cnt))
                    raise
                if not res:
                    break
                cond = await executor.eval_expr(function, f"{path}.{AgentWords.condition}", command.param(AgentWords.condition))
                cnt += 1
                replay_index = -1 # Once the first loop is done, the while loop continues like normal
            executor.stream_iter.trace(lambda: f"While loop completed after {cnt - 1} iteration" + ("" if cnt == 2 else "s"), TraceType.flow, inv.path)


