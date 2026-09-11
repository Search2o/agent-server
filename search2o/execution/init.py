# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from search2o.common.rest_call import RestCall
from search2o.execution.agent_executor import Name2Command
from search2o.execution.runtime import Runtime
from search2o.models.schemaobjects import CommandName


class Init:

    @classmethod
    async def init_all(cls) -> None:
        await RestCall.init()

        from search2o.commands.api import ApiCommand
        from search2o.commands.ask import AskCommand
        from search2o.commands.breakv import BreakCommand
        from search2o.commands.continuev import ContinueCommand
        from search2o.commands.db import DbCommand
        from search2o.commands.fail import FailCommand
        from search2o.commands.func import FuncCommand
        from search2o.commands.parallel import ParallelCommand
        from search2o.commands.ifv import IfCommand
        from search2o.commands.llm import LlmCommand
        from search2o.commands.memory import MemoryCommand
        from search2o.commands.output import OutputCommand
        from search2o.commands.progress import ProgressCommand
        from search2o.commands.returnv import ReturnCommand
        from search2o.commands.whilev import WhileCommand
        from search2o.commands.end import EndCommand
        from search2o.commands.forv import ForCommand
        from search2o.commands.invoke import InvokeCommand
        from search2o.commands.log import LogCommand
        from search2o.commands.prompt import PromptCommand
        from search2o.commands.search import SearchCommand
        from search2o.commands.trace import TraceCommand
        from search2o.commands.var import VarCommand

        Name2Command.command_executors = {

            # Enterprise integration commands
            CommandName.api: ApiCommand(),
            CommandName.db: DbCommand(),

            # LLM commands
            CommandName.llm: LlmCommand(),
            CommandName.prompt: PromptCommand(),

            # Deep agents
            CommandName.search: SearchCommand(),
            CommandName.invoke: InvokeCommand(),

            # HITL
            CommandName.ask: AskCommand(),

            # Long term memory
            CommandName.memory: MemoryCommand(),

            # Control flow
            CommandName.ifv: IfCommand(),
            CommandName.whilev: WhileCommand(),
            CommandName.forv: ForCommand(),
            CommandName.func: FuncCommand(),
            CommandName.parallel: ParallelCommand(),
            CommandName.breakv: BreakCommand(),
            CommandName.continuev: ContinueCommand(),
            CommandName.returnv: ReturnCommand(),
            CommandName.end: EndCommand(),
            CommandName.fail: FailCommand(),

            # Variable
            CommandName.var: VarCommand(),

            # Info
            CommandName.trace: TraceCommand(),
            CommandName.progress: ProgressCommand(),
            CommandName.log: LogCommand(),

            # Agent output
            CommandName.output: OutputCommand(),


        }
        await Runtime.update()

    @classmethod
    async def close_all(cls):
        await RestCall.close()
        await Runtime.close()
