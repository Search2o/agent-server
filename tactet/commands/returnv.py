# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://tactet.com/legal/license.html.

from __future__ import annotations


from pydantic import JsonValue

from tactet.common.enums import TraceType
from tactet.common.flowcontrol import ReturnFunctionException
from tactet.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation


class ReturnCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, path = inv.frame, inv.command, inv.path
        val = await executor.scalar_value(function, command, path)
        executor.stream_iter.trace(lambda: f"Returning from function {function.name!r}: {str(val)[:500]}", TraceType.output, inv.path)
        raise ReturnFunctionException(val)
