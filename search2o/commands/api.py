# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import json

from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import SERVICE_RETRY, ShowMessage, ErrorInAgent, error_message
from search2o.common.mtimeout import m_timeout
from search2o.common.sensitivestring import SensitiveString
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation


class ApiCommand(CommandExec):
    default_headers = {
        "content-type": "application/json",
        "accept": "application/json",
    }

    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, path = inv.frame, inv.command, inv.command_ns, inv.path

        profile_name = executor.param(function, command, command_ns, AgentWords.profile, ExpectedType.strt)
        if profile_name:
            profile = executor.runtime.apis.get(profile_name)
            if profile:
                pool_name = profile.connectionPoolName
                url = await executor.eval_expr(function, f"{path}.profile.{profile_name}.url", profile.url, ExpectedType.strt)

                # headers are merged with what's specified in the agent
                profile_headers = await executor.eval_expr(function, f"{path}.profile.{profile_name}.headers", profile.headers, ExpectedType.dictstrt)
                agent_headers = executor.param(function, command, command_ns, AgentWords.headers, ExpectedType.dictstrt)
                if profile_headers:
                    headers = profile_headers
                    if agent_headers:
                        headers.update({k: v for k, v in agent_headers.items() if k not in profile_headers})
                elif agent_headers:
                    headers = agent_headers
                else:
                    headers = self.default_headers

            else:
                raise ShowMessage(f"API profile {profile_name} not found")
        else:
            pool_name = None
            url = executor.param(function, command, command_ns, AgentWords.url, ExpectedType.strt)
            headers: dict[str, JsonValue] = executor.param(function, command, command_ns, AgentWords.headers, ExpectedType.dictstrt)
            if not headers:
                headers = self.default_headers

        params = executor.param(function, command, command_ns, AgentWords.params, ExpectedType.dictstrt)
        body = executor.param(function, command, command_ns, AgentWords.body, ExpectedType.dictstrt)
        timeout = executor.param(function, command, command_ns, AgentWords.timeout, ExpectedType.intt)

        method = executor.param(function, command, command_ns, AgentWords.method, ExpectedType.strt)
        if not method:
            if body:
                method = "POST"
            else:
                method = "GET"

        executor.stream_iter.trace(lambda: f"Calling API with url = {SensitiveString.safe_url(url)}, "
                                   f"method = {method}, "
                                   f"headers={json.dumps(SensitiveString.safe_dict(headers), indent=2)}, "
                                   f"params={json.dumps(SensitiveString.safe_dict(params), indent=2)}, "
                                   f"body={json.dumps(SensitiveString.safe_dict(body), indent=2)}"
                                   , TraceType.input, inv.path)
        try:
            async with m_timeout(timeout): # If timeout is not specified, this does not enforce a timeout
                result = await executor.runtime.network.call_rest(pool_name, method, url, headers, params, body)
            if isinstance(result, dict):
                executor.stream_iter.trace(lambda: f"API returned: {json.dumps(result, indent=2)}", TraceType.output, inv.path)
            elif isinstance(result, str):
                executor.stream_iter.trace(lambda: f"API returned a text message: {result}", TraceType.output, inv.path)
            else:
                executor.stream_iter.trace(lambda: "API returned a binary object", TraceType.output, inv.path)
        except TimeoutError:
            executor.stream_iter.trace(lambda: "API call timed out", TraceType.error, inv.path)
            raise ShowMessage(f"Call to API {SensitiveString.safe_url(url)!r} timed out", SERVICE_RETRY)
        except ErrorInAgent:
            raise  # a real agent error (e.g. unknown API method) must not be relabeled as a comms failure
        except Exception as e:
            executor.stream_iter.trace(lambda e=e: f"Exception calling API: {error_message(e)}", TraceType.error, inv.path)
            raise ShowMessage(f"Could not communicate with API {SensitiveString.safe_url(url)!r}: {error_message(e)}",
                              SERVICE_RETRY)
        return result
