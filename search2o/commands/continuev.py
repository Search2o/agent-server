# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations


from pydantic import JsonValue

from search2o.common.enums import TraceType
from search2o.common.flowcontrol import ContinueException
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation


class ContinueCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, path = inv.frame, inv.command, inv.path
        cond = await executor.scalar_value(function, command, path,ExpectedType.boolt)
        if cond:
            executor.stream_iter.trace(lambda: "Continuing with the next iteration of the loop", TraceType.flow, inv.path)
            raise ContinueException()
