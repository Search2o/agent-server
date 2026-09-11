# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio
import json
import math
from itertools import islice
from typing import TYPE_CHECKING, Any, ClassVar

from fastapi import Request
from pydantic import BaseModel
from search2o.common.enums import TraceType
from search2o.common.epoch import Epoch
from search2o.common.exceptions import ShowMessage, error_message
from search2o.common.mylogger import MyLogger
from search2o.common.rest_call import RestCall
from search2o.common.sensitivestring import JsonValue
from search2o.execution.agent_state import AgentOutput, AgentRun, ConversationState
from search2o.execution.agentexec import AgentExec
from search2o.execution.encryptor import Encryptor
from search2o.execution.llmresponse import LlmResult, LlmTokens
from search2o.execution.runref import RunRef
from search2o.execution.runtime import RuntimeState, Runtime
from search2o.execution.statenodes import Node, FunctionNode, FuncCommandNode, InvokeCommandNode
from search2o.execution.streamiter import StreamIter
from search2o.models.apimodels import ErrorResponseModel, ExecAgentResponseModel
from search2o.models.prompt import LlmResponseModel, ToolCalls
from search2o.models.schemaobjects import AgentExecResult, ReadOnlyVariable

if TYPE_CHECKING:
    from search2o.execution.agent_executor import ExecResponse

class ExecStartResponseModel(BaseModel):
    convid: str | None = None
    userEmail: str
    configUpdatedAt: int = 0
    isValidationRun: bool = False

_MEMORY_TEXT_MAX = 1000
_MEMORY_AGENTS_MAX = 10
_ERROR_MESSAGE_MAX = 2048
_PATH_MAX = 2048


class ConversationRun:
    def __init__(self, request: Request,
                 convid: str,
                 user_email: str,
                 stream_iter: StreamIter,
                 run_ref: RunRef | None,
                 runtime: RuntimeState,
                 agent_exec: AgentExec,
                 inputs: dict[str, Any],
                 conversation_state: ConversationState | None = None,
                 is_validation_run: bool = False) -> None:
        self.request = request
        self.convid = convid
        self.user_email = user_email
        self.stream_iter = stream_iter
        self.run_ref = run_ref
        self.runtime = runtime
        self.is_validation_run = is_validation_run
        self.conversation_state = conversation_state if conversation_state else ConversationState()

        runs = self.conversation_state.runs
        if runs and runs[-1].callstack:
            last_run = runs[-1]
            self.paused_agent_name: str | None = last_run.agentName
            self.prev_state: list[Node] = last_run.callstack
            self.ask_answers: dict[str, Any] | None = inputs
            self.inputs: dict[str, Any] = last_run.inputs
        else:
            self.paused_agent_name = None
            self.prev_state = []
            self.ask_answers = None
            self.inputs = inputs
        self.query: str = self.inputs.get("query", "")

        self.agent_exec = agent_exec
        self.agent_name = agent_exec.agent_name
        self.agent_version = agent_exec.agent_version
        self.output = AgentOutput(agentName=agent_exec.agent_name)
        self.callstack: list[Node] = []
        self.exec_start_time = 0

        self.llm_calls: list[LlmResult] = []
        self.llmCost: float = 0.0
        self.llmDuration: float = 0.0
        self.memories_add: dict[str, dict[str, str]] = {}
        self.memories_remove: dict[str, list[str]] = {}

    @classmethod
    async def create(cls, request: Request, item: ExecStartResponseModel, inputs: dict[str, JsonValue],
                     agent_exec: AgentExec, stream_iter: StreamIter, state: str | None = None,
                     run_ref: RunRef | None = None) -> ConversationRun:
        runtime = Runtime.current()
        stream_iter.trace(lambda: f"Executing agent: {agent_exec.agent_title} ({agent_exec.agent_name})", TraceType.flow)
        conversation_state = None
        if state:
            conversation_state = ConversationState.model_validate_json(await Encryptor.decrypt(request, runtime, state))
        run = cls(request=request, convid=item.convid, user_email=item.userEmail,
                  stream_iter=stream_iter, run_ref=run_ref, runtime=runtime, agent_exec=agent_exec,
                  inputs=inputs, conversation_state=conversation_state,
                  is_validation_run=item.isValidationRun)
        return run

    @property
    def paused_on_another_agent(self) -> str:
        return self.paused_agent_name if self.paused_agent_name and self.paused_agent_name != self.agent_name else ""

    async def execute(self) -> ExecAgentResponseModel:
        from search2o.execution.agent_executor import AgentExecutor, ExecResponse

        self.exec_start_time = Epoch.ms()
        ae = AgentExecutor(run=self, agent_exec=self.agent_exec, inputs=self.inputs)
        try:
            async with asyncio.timeout(self.runtime.validation.maxAgentRuntime):
                er = await ae.exec_agent()
        except asyncio.TimeoutError:
            er = ExecResponse(result_code=AgentExecResult.timedOut,
                              error_message=f"Agent execution timed out after {self.runtime.validation.maxAgentRuntime} "
                                            f"seconds, as set in the configuration.")

        self.callstack = ae.callstack
        return self.response(await self.record(er))

    async def record(self, er: ExecResponse) -> ExecResponse:
        from search2o.execution.agent_executor import ExecResponse

        if not self.is_validation_run:
            try:
                await self.agent_executed(er)
            except Exception as e:
                MyLogger.error(f"Could not report the execution of agent {self.agent_name!r} in conversation "
                               f"{self.convid}: {error_message(e)}")
        if er.result_code in (AgentExecResult.success, AgentExecResult.ask):
            try:
                await self.save_state()
            except Exception as e:
                MyLogger.error(f"Could not save the state of agent {self.agent_name!r} in conversation "
                               f"{self.convid}: {error_message(e)}")
                if er.result_code == AgentExecResult.ask:
                    return ExecResponse(result_code=AgentExecResult.errorInAgent, output=self.output,
                                        error_message=f"The conversation could not be saved, so the agent's "
                                                      f"questions cannot be answered: {error_message(e)}",
                                        user_message="This conversation could not be saved. Please try again.")
        return er

    def add_llm_result(self, profile: str, model: str, res: LlmResponseModel, start_time: int):
        llm_duration = Epoch.ms() - start_time
        self.llm_calls.append(LlmResult(
            profile=profile,
            model=model,
            tool_call=isinstance(res.assistant.response, ToolCalls),
            input_tokens=LlmTokens(text=res.inputTextTokens, image=res.inputImageTokens),
            output_tokens=LlmTokens(text=res.outputTextTokens, image=res.outputImageTokens),
            duration=llm_duration
        ))
        llm_model = self.runtime.llm_options.get(profile).pricing
        # Configured prices are per million tokens (see ModelDetails in systemconfig.py).
        cost = math.sumprod((res.inputTextTokens, res.inputImageTokens, res.outputTextTokens, res.outputImageTokens),
                            (llm_model.inputText, llm_model.inputImage, llm_model.outputText, llm_model.outputImage)) / 1_000_000
        self.llmDuration += llm_duration
        self.llmCost += cost
        if self.llmCost > self.runtime.validation.maxLlmPrice:
            raise ShowMessage(f"Agent LLM cost exceeded the total set per run: {self.runtime.validation.maxLlmPrice}",
                              "This request was stopped because it reached the cost limit set for this agent.")

    ENCRYPTED_QUERY_MAX: ClassVar[int] = 200

    @classmethod
    def conversation_title(cls, query: str) -> str:
        if len(query) <= cls.ENCRYPTED_QUERY_MAX:
            return query
        head = query[:cls.ENCRYPTED_QUERY_MAX]
        cut = head.rfind(" ")
        return head[:cut] if cut > 0 else head

    def remember(self, agent_name: str, label: str, text: str) -> None:
        if len(text) > _MEMORY_TEXT_MAX:
            MyLogger.warning(f"Memory {label!r} stored by agent {agent_name!r} is {len(text)} characters and was "
                             f"truncated to {_MEMORY_TEXT_MAX}.")
            text = text[:_MEMORY_TEXT_MAX]
        self.memories_add.setdefault(agent_name, {})[label] = text

    def forget(self, agent_name: str, labels: list[str]) -> None:
        remembered = self.memories_remove.setdefault(agent_name, [])
        remembered.extend(label for label in labels if label not in remembered)

    async def encrypted_memories(self, add: dict[str, dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
        """The cloud embeds `text` and stores only `encrypted`, so each memory carries both."""
        return {agent: {label: {"text": text,
                                "encrypted": await Encryptor.encrypt(self.request, self.runtime, text)}
                        for label, text in labels.items()}
                for agent, labels in add.items()}

    @staticmethod
    def capped_memories(memories: dict[str, Any], what: str) -> dict[str, Any]:
        if len(memories) <= _MEMORY_AGENTS_MAX:
            return memories
        kept = dict(islice(memories.items(), _MEMORY_AGENTS_MAX))
        MyLogger.warning(f"{len(memories)} agents {what} memories in this run; only the first "
                         f"{_MEMORY_AGENTS_MAX} are kept: {', '.join(sorted(set(memories) - set(kept)))} dropped.")
        return kept

    def check_serialization_errors(self) -> str:
        errors: list[str] = []
        agent_vars = self.conversation_state.agentVars.get(self.agent_name)
        namespaces = [(self.conversation_state.conversationVars, ReadOnlyVariable.conv)]
        if agent_vars is not None:
            namespaces.insert(0, (agent_vars, ReadOnlyVariable.agent))
        for (ns, name) in namespaces:
            for k, v in vars(ns).items():
                try:
                    json.dumps(v)
                except (TypeError, ValueError) as e:
                    errors.append(f"{name}.{k} is not serializable: {e}")
        self.check_callstack_errors(self.callstack, errors)
        return "\n".join(errors)

    def check_callstack_errors(self, nodes: list[Node], errors: list[str]) -> None:
        for node in nodes:
            if isinstance(node, FunctionNode):
                self.check_values_lost(node.localVars, f"Local variable in function {node.name!r}", errors)
                self.check_values_lost(node.args, f"Argument of function {node.name!r}", errors)
            elif isinstance(node, FuncCommandNode):
                self.check_values_lost(node.args, f"Argument to the call of function {node.name!r}", errors)
            elif isinstance(node, InvokeCommandNode):
                self.check_values_lost(node.inputs, f"Input to the invoked agent {node.agent_name!r}", errors)
                self.check_callstack_errors(node.nodes, errors)

    @staticmethod
    def check_values_lost(values: dict[str, Any], what: str, errors: list[str]) -> None:
        for k, v in values.items():
            try:
                json.dumps(v)
            except (TypeError, ValueError) as e:
                errors.append(f"{what}, {k!r}, is not serializable and will be lost while the agent waits for the user: {e}")

    def serialize(self) -> str:
        if self.stream_iter.should_trace or self.runtime.validation.checkSerializationErrors:
            errors = self.check_serialization_errors()
            if errors:
                self.stream_iter.trace(lambda: errors, TraceType.error)
                MyLogger.warning(f"Agent {self.agent_name!r} in conversation {self.convid}: {errors}")
        cr = AgentRun(inputs=self.inputs,
                      agentName=self.agent_name, agentVersion=self.agent_version,
                      output=self.output, execAt=Epoch.ms(), callstack=self.callstack)
        self.conversation_state.runs.append(cr)
        return self.conversation_state.model_dump_json(warnings=False, fallback=lambda _v: {})

    async def agent_executed(self, res: ExecResponse):
        duration = Epoch.ms() - self.exec_start_time if self.exec_start_time else 0
        query_en = await Encryptor.encrypt(self.request, self.runtime, self.conversation_title(self.query))
        d = {
            "agentName": self.agent_name,
            "agentVersion": self.agent_version, # zero for validation runs
            "convid": self.convid,
            "query": query_en,
            "duration": duration,
            "resultCode": res.result_code,
            "errorMessage": res.error_message[:_ERROR_MESSAGE_MAX],
            "path": res.path[-_PATH_MAX:],
            "llmCost": self.llmCost,
            "llmDuration": self.llmDuration,
            "memories": {"add": await self.encrypted_memories(self.capped_memories(self.memories_add, "stored")),
                         "remove": self.capped_memories(self.memories_remove, "deleted")}
        }
        await RestCall.call_method(self.request, "agentExecuted", d)

    async def save_state(self):
        state = self.serialize()
        state_en = await Encryptor.encrypt(self.request, self.runtime, state)
        await RestCall.save_state(self.request, self.convid, state_en)

    def response(self, er: ExecResponse) -> ExecAgentResponseModel:
        title = f"{self.agent_exec.agent_title} ({self.agent_name})"
        if er.result_code == AgentExecResult.success:
            self.stream_iter.trace(lambda: f"Executed agent: {title} successfully", TraceType.flow)
            return ExecAgentResponseModel(convid=self.convid, agentName=self.agent_name,
                                          resultCode=er.result_code, output=self.output)
        if er.result_code == AgentExecResult.ask:
            self.stream_iter.trace(lambda: f"Agent waiting for additional input: {title}", TraceType.flow)
            return ExecAgentResponseModel(convid=self.convid, agentName=self.agent_name,
                                          resultCode=er.result_code, output=self.output, askInput=er.ask_input)
        if er.result_code == AgentExecResult.stopped:
            self.stream_iter.trace(lambda: f"Stopped agent: {title}", TraceType.flow)
            return ExecAgentResponseModel(success=False, convid=self.convid, agentName=self.agent_name,
                                          resultCode=er.result_code, errorMessage=er.error_message, output=self.output)
        if er.result_code == AgentExecResult.timedOut:
            self.stream_iter.progress(f"{title} timed out")
        else:
            self.stream_iter.progress(f"{title} failed")
        user_facing = er.user_message if er.user_message and not self.is_validation_run else er.error_message
        return ExecAgentResponseModel(success=False, agentName=self.agent_name, resultCode=er.result_code,
                                      error=ErrorResponseModel(message=user_facing) if user_facing else None)
