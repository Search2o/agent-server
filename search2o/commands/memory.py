# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations


from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import ShowMessage
from search2o.common.rest_call import RestCall
from search2o.execution.encryptor import Encryptor
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation


class MemoryCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns = inv.frame, inv.command, inv.command_ns
        store = executor.param(function, command, command_ns, AgentWords.store, ExpectedType.dictstrt)
        delete = executor.param(function, command, command_ns, AgentWords.delete, ExpectedType.liststrt)
        query = executor.param(function, command, command_ns, AgentWords.query, ExpectedType.strt)

        if store:
            for label, text in store.items():
                if not isinstance(text, str) or not text:
                    raise ShowMessage(f"In function {function.name!r}, command {command.qn()}, the memory "
                                      f"{label!r} must evaluate to a non-empty string")
                executor.remember(label, text)
            executor.stream_iter.trace(lambda: f"Remembering {sorted(store)} for the user", TraceType.output, inv.path)

        if delete:
            executor.forget(delete)
            executor.stream_iter.trace(lambda: f"Forgetting {delete} for the user", TraceType.output, inv.path)

        if not query:
            return None

        params: dict[str, JsonValue] = {AgentWords.query: query}
        for key, expected in ((AgentWords.agentName, ExpectedType.strt),
                              (AgentWords.label, ExpectedType.strt),
                              (AgentWords.limit, ExpectedType.intt)):
            value = executor.param(function, command, command_ns, key, expected)
            if value:
                params[key] = value
        executor.stream_iter.trace(lambda: f"Searching the user's memory with {params}", TraceType.input, inv.path)
        ret = await RestCall.call_method(executor.request, "getMemory", params)
        memories = ret.get("memories")
        for memory in memories or []:
            try:
                memory["text"] = await Encryptor.decrypt(executor.request, executor.runtime,
                                                                  memory["text"])
            except Exception:
                memory["text"] = "Decryption error"
        executor.stream_iter.trace(lambda: f"Memory returned {len(memories) if memories else 0} entries",
                                   TraceType.output, inv.path)
        return memories
