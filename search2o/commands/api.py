# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import json
from urllib.parse import urlparse

from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import SERVICE_RETRY, ShowMessage, ErrorInAgent, error_message
from search2o.common.mtimeout import m_timeout
from search2o.common.sensitivestring import SensitiveString
from search2o.common.typechecker import ExpectedType
from search2o.common.urlquery import split_query
from search2o.execution.agent_executor import AgentExecutor, CommandExec, CommandInvocation
from search2o.models.systemconfig import ApiServerModel, PathAdd


class ApiCommand(CommandExec):
    default_headers = {
        "content-type": "application/json",
        "accept": "application/json",
    }

    @staticmethod
    def join_url(base: str, url: str) -> str:
        if not base:
            return url
        return f"{base.rstrip('/')}/{url.lstrip('/')}"

    @staticmethod
    def check_relative_path(profile_name: str, profile: ApiServerModel, url: str) -> None:
        if profile.addPath == PathAdd.cannot:
            raise ShowMessage(f"The API profile {profile_name!r} does not allow a path to be added to its URL.")
        parts = urlparse(url)
        if parts.scheme or parts.netloc:
            raise ShowMessage(f"The url of an api command that uses the API profile {profile_name!r} must be a "
                              f"relative path, not an absolute URL.")
        if ".." in parts.path.split("/"):
            raise ShowMessage(f"The url of an api command that uses the API profile {profile_name!r} cannot step "
                              f"outside the profile's URL with '..'.")

    @staticmethod
    def merge_headers(profile_name: str, profile: ApiServerModel, profile_headers: dict[str, JsonValue],
                      agent_headers: dict[str, JsonValue] | None) -> dict[str, JsonValue]:
        headers = dict(profile_headers)
        if not agent_headers:
            return headers
        by_lower = {name.lower(): name for name in profile_headers}
        for name, value in agent_headers.items():
            in_profile = by_lower.get(name.lower())
            if in_profile is not None:
                if not profile.headers[in_profile].override:
                    raise ShowMessage(f"The API profile {profile_name!r} does not allow the header "
                                      f"{in_profile!r} to be changed.")
                headers[in_profile] = value
            elif profile.canAddHeaders:
                headers[name] = value
            else:
                raise ShowMessage(f"The API profile {profile_name!r} does not allow the header {name!r} to be added.")
        return headers

    @staticmethod
    def merge_query_params(profile_name: str, profile: ApiServerModel, base_params: dict[str, JsonValue],
                           profile_params: dict[str, JsonValue],
                           agent_params: dict[str, JsonValue] | None) -> dict[str, JsonValue]:
        params = {**base_params, **profile_params}
        if not agent_params:
            return params
        for name, value in agent_params.items():
            if name in profile.queryParams:
                if not profile.queryParams[name].override:
                    raise ShowMessage(f"The API profile {profile_name!r} does not allow the query parameter "
                                      f"{name!r} to be changed.")
            elif name in base_params:
                raise ShowMessage(f"The API profile {profile_name!r} sets the query parameter {name!r} in its URL, "
                                  f"so it cannot be changed.")
            elif not profile.canAddQueryParams:
                raise ShowMessage(f"The API profile {profile_name!r} does not allow the query parameter "
                                  f"{name!r} to be added.")
            params[name] = value
        return params

    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, path = inv.frame, inv.command, inv.command_ns, inv.path

        agent_url = executor.param(function, command, command_ns, AgentWords.url, ExpectedType.strt)
        agent_headers = executor.param(function, command, command_ns, AgentWords.headers, ExpectedType.dictstrt)
        agent_params = executor.param(function, command, command_ns, AgentWords.queryParams, ExpectedType.dictstrt)

        profile_name = executor.param(function, command, command_ns, AgentWords.profile, ExpectedType.strt)
        if profile_name:
            profile = executor.runtime.apis.get(profile_name)
            if not profile:
                raise ShowMessage(f"API profile {profile_name} not found")
            pool_name = profile.connectionPoolName
            url = await executor.eval_expr(function, f"{path}.profile.{profile_name}.url", profile.url, ExpectedType.strt)
            url, base_params = split_query(url)
            agent_url_params: dict[str, JsonValue] = {}
            if agent_url:
                self.check_relative_path(profile_name, profile, agent_url)
                agent_url, agent_url_params = split_query(agent_url)
                url = self.join_url(url, agent_url)
            elif profile.addPath == PathAdd.must:
                raise ShowMessage(f"The API profile {profile_name!r} requires the api command to add a path to its URL.")

            profile_headers = await executor.eval_expr(
                function, f"{path}.profile.{profile_name}.headers",
                {name: value.value for name, value in profile.headers.items()}, ExpectedType.dictstrt)
            headers = self.merge_headers(profile_name, profile, profile_headers, agent_headers)

            profile_params = await executor.eval_expr(
                function, f"{path}.profile.{profile_name}.queryParams",
                {name: value.value for name, value in profile.queryParams.items()}, ExpectedType.dictstrt)
            params = self.merge_query_params(profile_name, profile, base_params, profile_params,
                                             {**agent_url_params, **(agent_params or {})})
        else:
            pool_name = None
            url, base_params = split_query(agent_url)
            headers = agent_headers
            params = {**base_params, **(agent_params or {})}

        if not headers:
            headers = self.default_headers

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
                                   f"queryParams={json.dumps(SensitiveString.safe_dict(params), indent=2)}, "
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
