# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations


from pydantic import JsonValue

from search2o.common.enums import AgentWords
from search2o.common.mylogger import MyLogger
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation


class LogCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns = inv.frame, inv.command, inv.command_ns
        name = executor.param(function, command, command_ns, AgentWords.name, ExpectedType.strt)
        level = executor.param(function, command, command_ns, AgentWords.level, ExpectedType.strt)
        message = executor.param(function, command, command_ns, AgentWords.message, ExpectedType.strt)
        MyLogger.log(name, level, message)
