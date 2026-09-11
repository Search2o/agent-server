# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import ShowMessage
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, AskException, CommandExec, CommandInvocation


class ForCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, path = inv.frame, inv.command, inv.command_ns, inv.path
        yield_after = executor.runtime.validation.yieldLoopsAfter
        iterable: Any = executor.param(function, command, command_ns, AgentWords.iter, ExpectedType.anyt)
        iterable_kind = type(iterable).__name__
        is_async = False
        try:
            iterable = aiter(iterable)
            is_async = True
        except TypeError:
            try:
                iterable = iter(iterable)
                is_async = False
            except TypeError:
                raise ShowMessage(f"In function {function.name!r}, command {command.qn()}, {AgentWords.iter} is a "
                                  f"{iterable_kind} and cannot be iterated over: {str(iterable)[:100]}")

        doit = command.command_list(AgentWords.do)
        if not doit:
            return

        index = 1 # This is not exposed in JSON
        index_names = executor.param(function, command, command_ns, AgentWords.loopVar, ExpectedType.strorliststrt)
        if isinstance(index_names, str):
            index_names = [index_names]
        max_iterations = executor.param(function, command, command_ns, AgentWords.maxIterations, ExpectedType.intt)
        if not max_iterations:
            max_iterations = executor.runtime.validation.maxIterationLoops

        executor.stream_iter.trace(lambda: f"For loop over a {iterable_kind}, binding {index_names}, "
                                           f"at most {max_iterations} iterations", TraceType.flow, inv.path)
        while True:
            if index % yield_after == 0:
                await asyncio.sleep(0)
            try:
                val = await anext(iterable) if is_async else next(iterable)
            except (StopIteration, StopAsyncIteration):
                break
            if index > max_iterations:
                break
            if isinstance(val, tuple):
                m = min(len(val), len(index_names))
                for i in range(m):
                    executor.set_iter(function, index_names[i], val[i])
            else:
                executor.set_iter(function, index_names[0], val)

            try:
                res = await executor.exec_command_list(function, doit, path)
            except AskException:
                raise ShowMessage("The 'ask' command cannot be used inside a 'for' loop, because a 'for' loop cannot resume where it left off after the agent pauses. Use a 'while' loop with an index variable instead.")
            if not res:
                break
            index += 1
        executor.stream_iter.trace(lambda: f"For loop completed after {index - 1} iteration" + ("" if index == 2 else "s"), TraceType.flow, inv.path)
        if index_names:
            if isinstance(index_names, list):
                for name in index_names:
                    executor.remove_iter(function, name)
            if isinstance(index_names, str):
                executor.remove_iter(function, index_names)

