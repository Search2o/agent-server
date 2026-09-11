# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from fastapi import Request
from httpx import AsyncClient, Response
from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.epoch import Epoch
from search2o.common.exceptions import AGENT_PROBLEM, ShowMessage, LlmError, error_message
from search2o.common.flowcontrol import AgentDone, FailCommandException, AgentStopped
from search2o.common.mtimeout import m_timeout
from search2o.common.mylogger import MyLogger
from search2o.common.sensitivestring import SensitiveString
from search2o.common.toolcallmethods import ToolCallMethods
from search2o.common.toolresponse import ToolResponse
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, AskException, CommandExec, FunctionFrame, CommandInvocation
from search2o.execution.llmresponse import LlmResponse
from search2o.execution.prompts import PromptHelper
from search2o.execution.statenodes import LlmCommandNode
from search2o.llm.llmcontext import LlmContext
from search2o.mcpclient.mcp import Mcp
from search2o.models.agentexecmodel import CommandExecModel
from search2o.models.prompt import LlmRequestModel, AgentFunctionModel, AssistantResponse, ToolCalls, ToolResults, ToolResult, \
    ContentOutput, LlmResponseModel
from search2o.models.schemaobjects import CommandName
from search2o.models.systemconfig import LlmModel


class LlmCommand(CommandExec):
    @staticmethod
    async def get_prompt_name(task: FunctionFrame, command: CommandExecModel, executor: AgentExecutor, command_ns: SimpleNamespace) -> str:
        name = executor.param(task, command, command_ns, AgentWords.prompt, ExpectedType.strt)
        return name if name else AgentWords.default.value

    @staticmethod
    async def get_mcp(task: FunctionFrame, executor: AgentExecutor, mcp_name: str, path: str) -> Mcp:
        async with executor.mcp_lock:
            mcp = executor.mcps.get(mcp_name)
            if not mcp:
                model = executor.runtime.mcp_servers.get(mcp_name)
                if not model:
                    raise ShowMessage(f"Unknown MCP server {mcp_name}")
                headers = await executor.eval_expr(task, f"{path}.mcp.{mcp_name}.headers", model.headers, ExpectedType.dictstrt)
                mcp = await Mcp.create(model, headers, executor.stream_iter)
                executor.mcps[mcp_name] = mcp
            return mcp


    async def set_tools_and_tasks(self, function_exec: FunctionFrame, command: CommandExecModel, executor: AgentExecutor,
                                  llmreq: LlmRequestModel, profile: LlmModel, command_ns: SimpleNamespace, path: str)-> None:
        functions = executor.param(function_exec, command, command_ns, AgentWords.functions, ExpectedType.liststrt)
        mcp = executor.param(function_exec, command, command_ns, AgentWords.mcp, ExpectedType.liststrt)
        vendor_tools = executor.param(function_exec, command, command_ns, AgentWords.vendorTools, ExpectedType.listt)
        if functions or mcp or vendor_tools:
            if functions:
                for func in functions:
                    function = executor.agent.functions.get(func)
                    if not function:
                        raise LlmError(f"{func} is not a function in this agent.", AGENT_PROBLEM)
                    if not function.description:
                        raise LlmError(f"Function {function.name} must provide a description to be included in the LLM tools list",
                           AGENT_PROBLEM)
                    task_model = AgentFunctionModel(name=ToolCallMethods.function_name(function.name),
                                                    description=function.description,
                                                    parameters=function.args if function.args is not None else {})
                    llmreq.agentFunctions.append(task_model)

            if mcp:
                for m in mcp:
                    prefix, _, suffix = m.partition(".")
                    if prefix:
                        mcp = await self.get_mcp(function_exec, executor, prefix, path)
                        if suffix:
                            tool = mcp.get_tool(suffix)
                            if tool:
                                llmreq.mcpTools.append(tool)
                            else:
                                raise ShowMessage(f"Unknown MCP tool {m}")
                        else:
                            tools = mcp.get_all_tools()
                            for tool in tools:
                                llmreq.mcpTools.append(tool)
                            executor.stream_iter.trace(lambda: f"Added all the tools from MCP {prefix}", TraceType.tool, path)

            if vendor_tools:
                for vendor_tool in vendor_tools:
                    llmreq.vendorTools.append(vendor_tool)

            if len(llmreq.mcpTools) + len(llmreq.agentFunctions) > profile.maxTools:
                raise ShowMessage(f"Too many tools used in agent {executor.agent_name}. Max allowed is {profile.maxTools} in the LLM profile.")

    @staticmethod
    async def execute_task(executor: AgentExecutor, task_name: str, arg_values: dict[str, JsonValue],
                           replay_index: int = -1) -> ToolResponse:
        try:
            resp = await executor.exec_function(task_name, arg_values, replay_index)
            if isinstance(resp, ToolResponse):
                return resp
            elif isinstance(resp, dict):
                try:
                    json.dumps(resp)
                    return ToolResponse(success=True, response=resp)
                except (TypeError, ValueError):
                    executor.stream_iter.trace(lambda: f"Tool {task_name!r} returned a value that is not JSON. "
                                                       f"It is sent to the LLM as text, so its structure is lost.", TraceType.error)
            return ToolResponse(success=True, response={ "result": str(resp) })
        except (AgentStopped, AskException, FailCommandException):
            raise
        except AgentDone:
            raise ShowMessage(f"{CommandName.end} command is not allowed inside tool calls.")
        except Exception as e:
            return ToolResponse(success=False, recoverable=False, error_message=error_message(e))


    @staticmethod
    async def set_dynamic_config(task: FunctionFrame, command: CommandExecModel, executor: AgentExecutor, llmreq: LlmRequestModel,
                                 model_config: LlmModel, llm_name: str, command_ns: SimpleNamespace, path: str):
        llmreq.vendor = model_config.vendor
        llmreq.model = model_config.model
        llmreq.retries = model_config.retries
        llmreq.maxTokens = model_config.maxTokens

        llmreq.url = await executor.eval_expr(task, f"{path}.profile.{llm_name}.url", model_config.url, ExpectedType.strt)
        llmreq.headers = await executor.eval_expr(task, f"{path}.profile.{llm_name}.headers", model_config.headers, ExpectedType.dictstrt)
        llmreq.additionalParams = await executor.eval_expr(task, f"{path}.profile.{llm_name}.additionalParams", model_config.additionalParams, ExpectedType.dictstrt)


    @staticmethod
    def get_context(executor: AgentExecutor, llm_name: str):
        if llm_name:
            context = executor.runtime.llm_connections.contexts.get(llm_name)
            if not context:
                raise ShowMessage(f"Could not find LLM profile {llm_name}")
        else:
            context = executor.runtime.llm_connections.contexts.get(AgentWords.default)
            if not context:
                raise ShowMessage(f"If an LLM profile is not specified, an LLM profile called {AgentWords.default.value!r} is required.")
        return context

    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> Any:
        function, command, command_ns, path, replay_index = inv.frame, inv.command, inv.command_ns, inv.path, inv.replay_index
        node = executor.get_node(replay_index, LlmCommandNode)
        if node:
            replay_index += 1
        prompt_name = await self.get_prompt_name(function, command, executor, command_ns)
        stream_output = executor.param(function, command, command_ns, AgentWords.streamOutput, ExpectedType.boolt)
        llm_name = executor.param(function, command, command_ns, AgentWords.profile, ExpectedType.strt)
        timeout = executor.param(function, command, command_ns,AgentWords.timeout, ExpectedType.intt)
        max_tool_call_loops = executor.param(function, command, command_ns, AgentWords.maxToolCallLoops, ExpectedType.intt)
        output_format = executor.param(function, command, command_ns, AgentWords.outputFormat, ExpectedType.strt)

        with PromptHelper(executor.prompts, prompt_name) as prompt_helper:
            prompt = prompt_helper.prompt

            llmreq: LlmRequestModel = LlmRequestModel(prompt=prompt)
            context = self.get_context(executor, llm_name)
            model_config = context.llm
            await self.set_tools_and_tasks(function, command, executor, llmreq, model_config, command_ns, path)
            await self.set_dynamic_config(function, command, executor, llmreq, model_config, llm_name, command_ns, path)

            tool_call_count = node.toolCallCount if node else 0
            got_asst_response = False
            if node:
                prompt.system = node.systemPrompt
                prompt.elements[:] = node.elements
                nof_prompt_elements = node.elementCount
            else:
                nof_prompt_elements = len(prompt.elements)
            try:
                while tool_call_count < max_tool_call_loops:
                    if node:
                        asst = node.elements[-1]
                        if not isinstance(asst, AssistantResponse) or not isinstance(asst.response, ToolCalls):
                            raise ShowMessage("Unexpected type error in accepting user's responses.")
                        executor.stream_iter.trace(lambda: "Continuing the tool calls the LLM had already returned", TraceType.flow, inv.path)
                        tool_replay_index = replay_index
                    else:
                        executor.stream_iter.trace(lambda: f"Calling LLM, request = {json.dumps(SensitiveString.safe_dict(llmreq.model_dump()), indent=2)}", TraceType.input, inv.path)
                        llm_start_time = Epoch.ms()
                        llmres = await self.call_llm(executor.request, llmreq, context,
                                                       executor.runtime.network.get_pool(context.llm.connectionPoolName),
                                                       executor.agent_name, executor.agent_version,
                                                       executor.convid, timeout)
                        executor.add_llm_result(llm_name, llmreq.model, llmres, llm_start_time)
                        executor.stream_iter.trace(lambda: f"LLM call completed. LLM tokens: "
                                                   f"input text tokens = {llmres.inputTextTokens}, "
                                                   f"input image tokens = {llmres.inputImageTokens}, "
                                                   f"output text tokens = {llmres.outputTextTokens}, "
                                                   f"output image tokens = {llmres.outputImageTokens}", TraceType.output, inv.path)
                        asst = llmres.assistant
                        prompt_helper.add_assistant(asst)
                        tool_replay_index = -1

                    if isinstance(asst.response, ToolCalls):
                        if not node and output_format == AgentWords.structured:
                            return LlmResponse(llmres).get_tool_calls()
                        trs = ToolResults(responses=[])
                        tool_succeeded = True
                        tool_names = []
                        for tool in asst.response.tools:
                            prefix, tool_name = ToolCallMethods.retrieve_name(tool.name) # LLM will be given "_" and not a "."
                            parsed_args = ToolCallMethods.get_tool_args(tool.args)
                            if not parsed_args:
                                executor.stream_iter.trace(lambda: f"LLM returned invalid or empty JSON arguments for tool {tool_name!r}", TraceType.error, inv.path)

                            if prefix == AgentWords.function:
                                executor.stream_iter.trace(lambda: f"Function {tool_name} with args {json.dumps(parsed_args, indent=2)}", TraceType.tool, inv.path)
                                if tool_name not in executor.agent.functions:
                                    raise ShowMessage(f"LLM returned an unknown function in the agent for tool call: {tool_name}")
                                tool_names.append((prefix, tool_name, parsed_args, None))
                            elif prefix == AgentWords.mcp:
                                prefix, tool_name = Mcp.get_split_name(tool_name)
                                executor.stream_iter.trace(lambda: f"MCP tool {prefix}.{tool_name} with args {json.dumps(parsed_args, indent=2)}", TraceType.tool, inv.path)
                                mcp = executor.mcps.get(prefix)
                                if not mcp:
                                    raise ShowMessage(f"Unexpected MCP call from LLM: {prefix}")
                                tool_names.append((prefix, tool_name, parsed_args, mcp))
                            else:
                                raise ShowMessage(f"Unexpected tool call type returned from LLM: {prefix}")

                        responses: list[ToolResponse] = list(node.responses) if node else []
                        node = None
                        for i in range(len(responses), len(tool_names)):
                            prefix, tool_name, parsed_args, mcp = tool_names[i]
                            if mcp:
                                response = await mcp.call_tool(tool_name, parsed_args, executor.stream_iter)
                            else:
                                try:
                                    response = await self.execute_task(executor, tool_name, parsed_args, tool_replay_index)
                                except AskException as e:
                                    e.append(LlmCommandNode(elements=list(prompt.elements), systemPrompt=prompt.system,
                                                            elementCount=nof_prompt_elements,
                                                            toolCallCount=tool_call_count, responses=responses))
                                    raise
                            tool_replay_index = -1
                            if not response.success and not response.recoverable:
                                raise ShowMessage(response.error_message)
                            responses.append(response) # For now, tool calling is serial

                        for i, tool_response in enumerate(responses):
                            tool = asst.response.tools[i]
                            prefix, tool_name, _args, _mcp = tool_names[i]

                            executor.stream_iter.trace(lambda: f"Call to {prefix} {tool_name} {"succeeded" if tool_response.success else "failed"} with the "
                                                               f"response: {json.dumps(tool_response.response, indent=2) if tool_response.success else tool_response.error_message}", TraceType.tool, inv.path)
                            tool_succeeded &= tool_response.success
                            if tool_response.success:
                                trs.responses.append(ToolResult(id=tool.id, name=tool.name, result=tool_response.response or {}))
                            else:
                                trs.responses.append(ToolResult(id=tool.id, name=tool.name, result={ "error": tool_response.error_message }, isError=True))
                        prompt_helper.add_tools(trs)
                        if not tool_succeeded:
                            prompt_helper.add_user(context.llm.toolErrorPrompt)
                        tool_call_count += 1
                    elif isinstance(asst.response, ContentOutput):
                        got_asst_response = True
                        executor.stream_iter.trace(lambda: f"LLM returned content: {asst.response.model_dump_json(indent=2, exclude_none=True)}", TraceType.output, inv.path)
                        if stream_output:
                            executor.add_output_part(LlmResponse(llmres))
                        return LlmResponse(llmres).get_text()

                raise ShowMessage(f"Max number of tool calls ({max_tool_call_loops}) exceeded.")
            finally:
                if not got_asst_response and len(prompt.elements) > nof_prompt_elements:
                    del prompt.elements[nof_prompt_elements:]

    @classmethod
    async def call_llm(
            cls,
            request: Request,
            req: LlmRequestModel,
            context: LlmContext,
            client: AsyncClient,
            agent_name: str,
            agent_version: int,
            convid: str,
            timeout: float | None,
    ) -> LlmResponseModel:
        attempts = max(1, req.retries + 1)

        llm_response: LlmResponseModel | None = None

        for attempt in range(attempts):
            is_last_attempt = attempt == attempts - 1

            try:
                response = await cls._send_llm_request(context, client, req, timeout)
                llm_response = cls._read_llm_response(context, req, response)

                if llm_response.did_succeed:
                    return llm_response

                if not llm_response.should_retry:
                    break

            except LlmError:
                if is_last_attempt:
                    raise

            if is_last_attempt:
                break

        failure_reason = llm_response.failure_reason if llm_response else "No response received."
        raise LlmError(
            f"LLM call to {req.vendor}/{req.model} failed. "
            f"LLM gave this failure reason: {failure_reason}"
        )


    @classmethod
    async def _send_llm_request(
            cls,
            context: LlmContext,
            client: AsyncClient,
            req: LlmRequestModel,
            timeout: float | None,
    ):
        try:
            js = context.adapter.process_request(req)

            async with m_timeout(timeout):
                return await client.post(req.url, headers=req.headers, json=js)

        except TimeoutError:
            raise LlmError(
                f"LLM call to {req.vendor}/{req.model} failed. "
                f"Timed out after {timeout} seconds."
            )

        except Exception as ex:
            message = f"LLM call to {req.vendor}/{req.model} failed. Transport error - {error_message(ex)}"
            MyLogger.error(message)
            raise LlmError(message)


    @classmethod
    def _read_llm_response(
            cls,
            context: LlmContext,
            req: LlmRequestModel,
            response: Response,
    ) -> LlmResponseModel:
        if response.status_code != 200:
            raise LlmError(
                f"LLM call to {req.vendor}/{req.model} failed. "
                f"Error message from the LLM: {cls._read_llm_error(context, req, response)}"
            )

        try:
            return context.adapter.process_response(req, response.json())
        except LlmError:
            raise  # preserve the adapter's specific failure reason
        except Exception:
            raise LlmError(
                f"LLM call to {req.vendor}/{req.model} failed. "
                f"Unexpected message from the LLM: {response.text}"
            )


    @classmethod
    def _read_llm_error(cls, context: LlmContext, req: LlmRequestModel, response: Response) -> str:
        try:
            return context.adapter.get_error(req, response.json())
        except ValueError:
            return f"HTTP {response.status_code}: {response.text[:500]}"
