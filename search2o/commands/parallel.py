# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio

from pydantic import JsonValue

from search2o.common.enums import TraceType
from search2o.common.exceptions import ShowMessage
from search2o.commands.func import FuncCommand
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation
from search2o.models.schemaobjects import CommandName


class ParallelCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        keys = list(inv.command.params)
        if not keys:
            raise ShowMessage(f"The {CommandName.parallel} command at {inv.path} has no functions to call.",
                              path=inv.path)
        calls = []
        for key in keys:
            args = getattr(inv.command_ns, key)
            calls.append((key, key.partition(".")[0], args if isinstance(args, dict) else {}))
        executor.stream_iter.trace(lambda: f"Calling {len(calls)} functions in parallel: {', '.join(keys)}",
                                   TraceType.flow, inv.path)
        try:
            async with asyncio.TaskGroup() as tg:
                tasks = [(key, tg.create_task(FuncCommand.call_function(executor, inv, name, fargs, -1)))
                         for key, name, fargs in calls]
        except BaseExceptionGroup as eg:
            raise self.unwrap_parallel(eg, executor)
        results = {key: task.result() for key, task in tasks}
        executor.stream_iter.trace(lambda: f"Parallel functions returned {str(results)[:500]}",
                                   TraceType.output, inv.path)
        return results
