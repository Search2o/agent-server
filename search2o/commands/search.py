# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from pydantic import JsonValue

from search2o.common.rest_call import RestCall
from search2o.common.enums import AgentWords, TraceType
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation
from search2o.models.apimodels import cloud_search_query


class SearchCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns = inv.frame, inv.command, inv.command_ns
        query = executor.param(function, command, command_ns, AgentWords.query, ExpectedType.strt)
        tag = executor.param(function, command, command_ns, AgentWords.tag, ExpectedType.strt)
        executor.stream_iter.trace(lambda: f"Searching for agents with query = {query!r}, tag = {tag!r}", TraceType.input, inv.path)
        ret = await RestCall.call_method(executor.request, "search", {
            "query": cloud_search_query(query),
            "tag": tag or ""
        })
        results = ret.get("searchResults")
        executor.stream_iter.trace(lambda: f"Search returned {len(results) if results else 0} agents: "
                                           f"{[r.get('agentName') for r in results] if results else []}", TraceType.output, inv.path)
        return results

