# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations


from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import ShowMessage
from search2o.common.sensitivestring import SensitiveString
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation


class DbCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, path = inv.frame, inv.command, inv.command_ns, inv.path
        profile_name = executor.param(function, command, command_ns, AgentWords.profile, ExpectedType.strt)
        connection_pool = None
        if profile_name:
            profile_config = executor.runtime.db_service.get(profile_name)
            if not profile_config:
                raise ShowMessage(f"Unknown database profile {profile_name}")
            connection_pool = profile_config.connectionPool
            connection_string = await executor.eval_expr(function, f"{path}.profile.{profile_name}.connectionString", profile_config.connectionString, ExpectedType.strt)
            if not connection_string:
                raise ShowMessage(f"Database profile {profile_name} does not specify a connection string")
        else:
            connection_string = executor.param(function, command, command_ns, AgentWords.connectionString, ExpectedType.strt)
            if not connection_string:
                raise ShowMessage(f"Must either specify a connection string or a {AgentWords.profile}")

        sql = executor.param(function, command, command_ns, AgentWords.sql, ExpectedType.strt)
        params = executor.param(function, command, command_ns, AgentWords.params, ExpectedType.dictstrt)
        timeout = executor.param(function, command, command_ns, AgentWords.timeout, ExpectedType.numbert)

        executor.stream_iter.trace(lambda: f"Calling Database with connection_string = {SensitiveString.safe_connection_string(connection_string)}, sql = {sql}", TraceType.input, inv.path)
        results =  await executor.runtime.db_connections.run_sql(profile_name, connection_pool, connection_string, sql, params, timeout)
        executor.stream_iter.trace(lambda: f"Database query returned {len(results)} rows", TraceType.output, inv.path)
        return results
