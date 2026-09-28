# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import JsonValue

from search2o.common.enums import TraceType
from search2o.common.exceptions import ShowMessage
from search2o.commands.func import FuncCommand
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation, AskException
from search2o.execution.statenodes import ParallelCommandNode, FuncCommandNode, Node
from search2o.models.apimodels import ASK_KEY
from search2o.models.schemaobjects import CommandName


class ParallelCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        keys = list(inv.command.params)
        if not keys:
            raise ShowMessage(f"The {CommandName.parallel} command at {inv.path} has no functions to call.",
                              path=inv.path)
        node = executor.get_node(inv.replay_index, ParallelCommandNode)
        results: dict[str, Any] = dict(node.results) if node else {}
        scope = executor.ask_answers
        calls = []
        for key in keys:
            if key in results:
                continue
            args = getattr(inv.command_ns, key)
            paused = node.paused.get(key) if node else None
            answers = scope.get(key) if isinstance(scope, dict) else None
            if paused and node.plainAsk.get(key):
                answers = {ASK_KEY: answers}
            calls.append((key, key.partition(".")[0], args if isinstance(args, dict) else {}, paused, answers))
        executor.stream_iter.trace(lambda: f"Calling {len(calls)} functions in parallel: "
                                           f"{', '.join(c[0] for c in calls)}"
                                           + (f" ({len(results)} already finished)" if results else ""),
                                   TraceType.flow, inv.path)
        try:
            async with asyncio.TaskGroup() as tg:
                tasks = [(key, tg.create_task(self.run_branch(executor, inv, name, fargs, paused, answers)))
                         for key, name, fargs, paused, answers in calls]
        except BaseExceptionGroup as eg:
            raise self.unwrap_parallel(eg, executor)
        asked: dict[str, AskException] = {}
        for key, task in tasks:
            value = task.result()
            if isinstance(value, AskException):
                asked[key] = value
            else:
                results[key] = value
        if asked:
            blocks: dict[str, Any] = {}
            paused_nodes: dict[str, list[Node]] = {}
            plain: dict[str, bool] = {}
            for key, ae in asked.items():
                is_plain = set(ae.ask_input) == {ASK_KEY}
                blocks[key] = ae.ask_input[ASK_KEY] if is_plain else ae.ask_input
                paused_nodes[key] = ae.nodes[::-1]
                plain[key] = is_plain
            executor.stream_iter.trace(lambda: f"Functions running in parallel are waiting for the user: "
                                               f"{', '.join(asked)}", TraceType.flow, inv.path)
            raise AskException(ParallelCommandNode(results=results, paused=paused_nodes, plainAsk=plain), blocks)
        ordered = {key: results[key] for key in keys}
        executor.stream_iter.trace(lambda: f"Parallel functions returned {str(ordered)[:500]}",
                                   TraceType.output, inv.path)
        return ordered

    @staticmethod
    async def run_branch(executor: AgentExecutor, inv: CommandInvocation, name: str, fargs: dict[str, JsonValue],
                         paused: list[Node] | None, answers: dict[str, Any] | None) -> Any:
        replay_index = -1
        if paused:
            AgentExecutor.set_branch_scope(paused, answers)
            first = executor.get_node(0, FuncCommandNode)
            name, fargs, replay_index = first.name, first.args, 1
        try:
            return await FuncCommand.call_function(executor, inv, name, fargs, replay_index)
        except AskException as e:
            return e
