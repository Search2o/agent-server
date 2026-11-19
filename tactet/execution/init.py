# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://tactet.com/legal/license.html.

from __future__ import annotations

import asyncio

from tactet.common.exceptions import error_message
from tactet.common.mylogger import MyLogger
from tactet.common.rest_call import RestCall
from tactet.config.config import Config
from tactet.execution.agent_executor import Name2Command
from tactet.execution.hooks import Hooks
from tactet.execution.runtime import Runtime
from tactet.models.schemaobjects import CommandName


class Init:
    started: bool = False

    @classmethod
    async def init_all(cls) -> None:
        await RestCall.init()
        Hooks.load(Config.init_model.hooks)
        if Hooks.errors:
            await RestCall.report_server_event("error", "Some hooks could not be loaded.")

        from tactet.commands.api import ApiCommand
        from tactet.commands.ask import AskCommand
        from tactet.commands.breakv import BreakCommand
        from tactet.commands.continuev import ContinueCommand
        from tactet.commands.db import DbCommand
        from tactet.commands.fail import FailCommand
        from tactet.commands.func import FuncCommand
        from tactet.commands.parallel import ParallelCommand
        from tactet.commands.ifv import IfCommand
        from tactet.commands.llm import LlmCommand
        from tactet.commands.memory import MemoryCommand
        from tactet.commands.output import OutputCommand
        from tactet.commands.progress import ProgressCommand
        from tactet.commands.returnv import ReturnCommand
        from tactet.commands.whilev import WhileCommand
        from tactet.commands.end import EndCommand
        from tactet.commands.forv import ForCommand
        from tactet.commands.log import LogCommand
        from tactet.commands.trace import TraceCommand
        from tactet.commands.var import VarCommand

        Name2Command.command_executors = {

            # Enterprise integration commands
            CommandName.api: ApiCommand(),
            CommandName.db: DbCommand(),

            # LLM commands
            CommandName.llm: LlmCommand(),

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
        await Hooks.call("onStart", lambda: {})
        cls.started = True

    @classmethod
    async def close_all(cls):
        await Runtime.stop_tasks(Config.init_model.agentServer.shutdownGrace)
        await asyncio.gather(*RestCall._report_tasks, return_exceptions=True)
        if cls.started:
            await RestCall.report_server_event("shutdown")
            try:
                await Hooks.call("onEnd", lambda: {})
            except Exception as e:
                message = f"The onEnd hook failed: {error_message(e)}"
                MyLogger.error(message)
                print(message, flush=True)
        await RestCall.close()
        await Runtime.close()
