# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from pydantic import JsonValue

from search2o.common.flowcontrol import AgentStopped
from search2o.execution.runtime import Runtime
from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import InvokedAgentFailed, ShowMessage
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, AskException, CommandInvocation
from search2o.execution.statenodes import InvokeCommandNode
from search2o.models.schemaobjects import AgentExecResult


class InvokeCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, replay_index = inv.frame, inv.command, inv.command_ns, inv.replay_index
        node = executor.get_node(replay_index, InvokeCommandNode)
        if node:
            inputs = node.inputs
            agent_name = node.agent_name
            share_prompts = node.share_prompts
        else:
            inputs = executor.param(function, command, command_ns, AgentWords.inputs, ExpectedType.dictstrt)
            agent_name = executor.param(function, command, command_ns, AgentWords.agent, ExpectedType.strt)
            share_prompts = executor.param(function, command, command_ns, AgentWords.sharePrompts, ExpectedType.boolt)

        agent_exec = await Runtime.get_agent(executor.request, agent_name)
        if node:
            agent_version = node.agent_version
            if agent_exec.agent_version != agent_version:
                raise ShowMessage(f'Agent {agent_name}, which is in the call chain, has been updated since the questions were asked. Please start over.')

        if agent_name in executor.agent_call_chain:
            raise ShowMessage(f"Circular invocation of the same agent: "
                              f"{' -> '.join([*executor.agent_call_chain, agent_name])}")

        executor.stream_iter.trace(lambda: f"Invoking agent {agent_name!r} version {agent_exec.agent_version} "
                                           f"with inputs {inputs if inputs else {}}, sharePrompts = {bool(share_prompts)}",
                                   TraceType.invoke, inv.path)
        ae = AgentExecutor(run=executor.run,
                           agent_exec=agent_exec,
                           inputs=inputs,
                           share_prompts=share_prompts,
                           agent_call_chain={*executor.agent_call_chain, agent_name})

        er = await ae.exec_agent(node.nodes if node else None)

        if er.result_code == AgentExecResult.success:
            executor.stream_iter.trace(lambda: f"Agent {agent_name} executed successfully and returned: {er.agent_return}. ", TraceType.invoke, inv.path)
            return er.agent_return
        elif er.result_code == AgentExecResult.ask:
            executor.stream_iter.trace(lambda: f"Agent {agent_name} is waiting for the user's answers", TraceType.invoke, inv.path)
            raise AskException(InvokeCommandNode(inputs=inputs, agent_name=agent_name,
                                                 agent_version=agent_exec.agent_version, share_prompts=share_prompts,
                                                 nodes=ae.callstack), ask_input=er.ask_input)
        elif er.result_code == AgentExecResult.stopped:
            executor.stream_iter.trace(lambda: f"Agent {agent_name} was stopped. ", TraceType.flow, inv.path)
            raise AgentStopped()
        elif er.platform_error:
            executor.stream_iter.trace(lambda: f"Agent {agent_name} failed with a platform error: {er.platform_error}. ", TraceType.error, inv.path)
            raise er.platform_error
        elif er.result_code == AgentExecResult.failCommand and er.error_message:
            executor.stream_iter.trace(lambda: f"Agent {agent_name} failed itself with the message: {er.error_message}. ", TraceType.error, inv.path)
            raise InvokedAgentFailed(er.error_message)
        elif er.error_message:
            executor.stream_iter.trace(lambda: f"Agent {agent_name} failed: {er.error_message}. ", TraceType.error, inv.path)
            raise ShowMessage(er.error_message)
        else:
            executor.stream_iter.trace(lambda: f"Agent {agent_name} failed with error code {er.result_code}, but did not set an error message", TraceType.error, inv.path)
            raise ShowMessage(f"Agent {agent_name} failed unexpectedly")
