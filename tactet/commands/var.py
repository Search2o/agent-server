# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://tactet.com/legal/license.html.

from __future__ import annotations


from pydantic import JsonValue

from tactet.common.enums import TraceType
from tactet.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation


class VarCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, path = inv.frame, inv.command, inv.path
        vallist = command.get_vars()
        assigned = []
        for aval in vallist:
            value = await executor.set_variable(function, aval, path)
            assigned.append(f"{aval.pn()} = {str(value)[:200]}")
        executor.stream_iter.trace(lambda: "Set " + ", ".join(assigned), TraceType.output, inv.path)

