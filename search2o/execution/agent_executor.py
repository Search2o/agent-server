# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio
import contextvars
from abc import ABC
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from typing import cast

from fastapi import Request
from pydantic import JsonValue

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import ErrorInAgent, ErrorFromCloudException, InvokedAgentFailed, ShowMessage, error_message
from search2o.common.exprhelper import ExprHelper
from search2o.common.flowcontrol import AgentStopped, BreakException, ContinueException, ReturnFunctionException, \
    AgentDone, FailCommandException, FlowControlException
from search2o.common.mynamespace import AgentNamespace, CommandNamespace
from search2o.common.requesthelper import RequestHelper
from search2o.common.rest_call import RestCall
from search2o.common.typechecker import ExpectedType, TypeChecker
from search2o.config.config import Config
from search2o.execution.agent_state import ConversationState, AgentOutput
from search2o.execution.agentexec import AgentExec
from search2o.execution.llmresponse import LlmResponse
from search2o.execution.prompts import Prompts
from search2o.execution.runtime import RuntimeState
from search2o.execution.secretsmanager import SecretsManager
from search2o.execution.statenodes import FunctionNode, CommandListNode, Node
from search2o.execution.streamiter import StreamIter
from search2o.mcpclient.mcp import Mcp
from search2o.models.agentexecmodel import FunctionExecModel, CommandExecModel, SetVariable, CommandList
from search2o.models.prompt import LlmResponseModel
from search2o.models.schemaobjects import CommandName, VarNamespace, ReadOnlyVariable, \
    AgentExecResult, AskInputsModel
from search2o.models.systemconfig import SysVariables

if TYPE_CHECKING:
    from search2o.execution.conversationrun import ConversationRun


@dataclass
class ExecResponse:
    result_code: AgentExecResult
    output: AgentOutput | None = None
    ask_input: AskInputsModel | None = None
    agent_return: Any = None
    error_message: str = ""
    user_message: str = ""
    path: str = ""
    platform_error: ErrorFromCloudException | None = None

class AskException(FlowControlException):
    def __init__(self, node: Node, ask_input: AskInputsModel):
        self.ask_input = ask_input
        self.nodes = []
        self.append(node)

    def append(self, node: Node):
        self.nodes.append(node)


class CommandExec(ABC):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        ...

    @staticmethod
    def unwrap_parallel(eg: BaseExceptionGroup, executor: AgentExecutor) -> BaseException:
        flat: list[BaseException] = []

        def collect(e: BaseException) -> None:
            if isinstance(e, BaseExceptionGroup):
                for sub in e.exceptions:
                    collect(sub)
            else:
                flat.append(e)

        collect(eg)
        stopped = next((e for e in flat if isinstance(e, AgentStopped)), None)
        asked = next((e for e in flat if isinstance(e, AskException)), None)
        if stopped or asked:
            chosen = stopped or asked
            for other in flat:
                if other is not chosen:
                    executor.stream_iter.trace(lambda other=other: f"Another command running in parallel also failed: {error_message(other)}", TraceType.error)
            return stopped or ShowMessage(f"The {CommandName.ask} command cannot be used in commands that run in parallel.")
        if len(flat) == 1:
            return flat[0]
        return ShowMessage(f"Commands running in parallel failed: "
                           f"{'; '.join(error_message(e) for e in flat)}")

@dataclass
class CommandInvocation:
    frame: "FunctionFrame"
    command: CommandExecModel
    command_ns: SimpleNamespace
    path: str
    replay_index: int = -1


class FunctionFrame:
    def __init__(self, model: FunctionExecModel, frame_locals: dict[str, Any]):
        self.model = model
        self.locals = frame_locals

    @property
    def name(self) -> str:
        return self.model.name

    @property
    def args(self):
        return self.model.args

    @property
    def commands(self):
        return self.model.commands

    @property
    def onError(self):
        return self.model.onError


_calling_path: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar("calling_path", default=frozenset())


class Name2Command:
    command_executors: dict[str, CommandExec] = {}

    @classmethod
    def get_command(cls, name: CommandName) -> CommandExec:
        return cls.command_executors.get(name)

class AgentExecutor:
    _RESULT_PRODUCING_COMMANDS = {
        CommandName.api, CommandName.db, CommandName.llm, CommandName.search, CommandName.invoke, CommandName.func,
        CommandName.ask, CommandName.memory, CommandName.parallel
    }

    def __init__(self, run: "ConversationRun",
                 agent_exec: AgentExec,
                 inputs: dict[str, Any],
                 share_prompts: bool = True,
                 agent_call_chain: set[str] | None = None) -> None:
        self.run = run
        self.agent_call_chain = agent_call_chain if agent_call_chain else set()

        self.agent = agent_exec.agent_definition
        self.agent_name = agent_exec.agent_name
        self.agent_version = agent_exec.agent_version

        if self.agent_name not in self.conversation_state.agentVars:
            self.conversation_state.agentVars[self.agent_name] = AgentNamespace()
        self.agent_vars = self.conversation_state.agentVars[self.agent_name]
        self.prompts = self.conversation_state.prompts if share_prompts else Prompts()
        self.current_stack: FunctionNode | None = None

        self.inputs = inputs
        self.prev_state = [] if self.agent_call_chain else run.prev_state
        self.query = self.get_query(self.inputs)
        self.args: dict[str, JsonValue] = {}

        self.callstack: list[Node] = []
        self.mcps: dict[str, Mcp] = {}
        self.mcp_lock = asyncio.Lock()
        self.sysvar = self.create_ro()

    @property
    def request(self) -> Request:
        return self.run.request

    @property
    def convid(self) -> str:
        return self.run.convid

    @property
    def user_email(self) -> str:
        return self.run.user_email

    @property
    def stream_iter(self) -> StreamIter:
        return self.run.stream_iter

    @property
    def run_ref(self):
        return self.run.run_ref

    @property
    def runtime(self) -> RuntimeState:
        return self.run.runtime

    @property
    def conversation_state(self) -> ConversationState:
        return self.run.conversation_state

    @property
    def output(self) -> AgentOutput:
        return self.run.output

    @property
    def ask_answers(self) -> dict[str, Any] | None:
        return self.run.ask_answers

    def remember(self, label: str, text: str) -> None:
        self.run.remember(self.agent_name, label, text)

    def forget(self, labels: list[str]) -> None:
        self.run.forget(self.agent_name, labels)

    def add_llm_result(self, profile: str, model: str, res: LlmResponseModel, start_time: int):
        self.run.add_llm_result(profile, model, res, start_time)

    @staticmethod
    def get_query(inputs: dict[str, Any]) -> str:
        return inputs.get("query", "")

    def set_iter(self, frame: FunctionFrame, name: str, value: JsonValue) -> None:
        self.set_variable_val(frame, name, value)

    def remove_iter(self, frame: FunctionFrame, name: str) -> None:
        self.remove_variable(frame, name)

    async def set_variable(self, frame: FunctionFrame, var: SetVariable, path: str) -> JsonValue:
        value = await self.eval_expr(frame, f"{path}.{var.pn()}", var.value, ExpectedType.anyt)
        match var.ns: # noop if it's not one of the below
            case VarNamespace.local: ns = frame.locals
            case VarNamespace.agent:
                namespace = self.agent_vars
                ns = vars(namespace)
            case VarNamespace.conv:
                my_namespace = self.conversation_state.conversationVars
                ns = vars(my_namespace)
            case _: return # Cannot happen after cloud validation

        if var.path:
            cur_path = var.name if var.ns == VarNamespace.local else f"{var.ns_str()}{var.name}"
            try:
                cur = ns[var.name]
            except KeyError:
                raise ShowMessage(
                    f"While setting variable at {path}: "
                    f"the base variable {cur_path!r} is not defined.", path=path
                ) from None


            evaluated_path: list[str | int] = [
                await self.eval_expr(
                    frame,
                    f"{path}.{var.pn()}",
                    key,
                    ExpectedType.strorintt,
                )
                if isinstance(key, str)
                else key
                for key in var.path
            ]

            for key in evaluated_path[:-1]:
                next_path = f"{cur_path}[{key!r}]"
                try:
                    cur = cur[key]
                except (KeyError, TypeError, IndexError) as e:
                    raise ShowMessage(
                        f"While setting variable at {path}: "
                        f"could not access {next_path}. "
                        f"{type(e).__name__}: {e}", path=path
                    ) from e
                cur_path = next_path

            key = evaluated_path[-1]
            target_path = f"{cur_path}[{key!r}]"

            try:
                cur[key] = value
            except (KeyError, TypeError, IndexError) as e:
                raise ShowMessage(
                    f"While setting variable at {path}: "
                    f"could not assign a value to {target_path}. "
                    f"{type(e).__name__}: {e}", path=path
                ) from e

        else:
            ns[var.name] = value
        return value

    # Local variables can be of any type. Agent and conv variables need to be of JsonValue types.
    def set_variable_val(self, frame: FunctionFrame, name: str, val: Any) -> None:
        frame.locals[name] = val

    def set_readonly_variable(self, frame: FunctionFrame, ro: ReadOnlyVariable, val: Any) -> None:
        frame.locals[ro] = val

    def get_readonly_variable(self, frame: FunctionFrame, ro: ReadOnlyVariable) -> Any:
        return frame.locals.get(ro)

    def remove_variable(self, frame: FunctionFrame, name: str) -> None:
        frame.locals.pop(name, None)

    async def scalar_value(self, function: FunctionFrame, command: CommandExecModel, path: str, expected_type: ExpectedType = ExpectedType.anyt) -> JsonValue:
        return await self.eval_expr(function, path, command.scalar_value, expected_type)

    def param(self, function: FunctionFrame, command: CommandExecModel, command_ns: SimpleNamespace, key: str,
                      expected_type: ExpectedType = ExpectedType.anyt) -> JsonValue:
        val = getattr(command_ns, key)
        if val is None or TypeChecker.check_type(expected_type, val):
            return val
        else:
            raise ShowMessage(f"In function {function.name!r}, command {command.qn()}, {str(key)!r} is expected to evaluate to a {expected_type} but it evaluated to {type(val).__name__}")

    async def prepare(self, frame: FunctionFrame, command: CommandExecModel, path: str,
                      replay_index: int = -1) -> CommandInvocation:
        path = f"{path}.{command.pn()}"
        self.stream_iter.trace(lambda: f"Executing command: {command.qn()}", TraceType.flow, path)
        command_ns = CommandNamespace()
        self.set_readonly_variable(frame, ReadOnlyVariable.command, command_ns)
        await self.set_command_params(frame, command, command_ns, path)
        return CommandInvocation(frame, command, command_ns, path, replay_index)

    async def set_command_params(self, function: FunctionFrame, command: CommandExecModel, command_ns: SimpleNamespace,
                                 path: str):
        for key, value in command.params.items():
            setattr(command_ns, key, await self.eval_expr(function, f"{path}.{key}", value, ExpectedType.anyt))

    async def eval_expr(self, frame: FunctionFrame, path: str, val: JsonValue, expected_type: ExpectedType = ExpectedType.anyt, sub_path: str = "") -> JsonValue:
        if not val:
            return val
        if isinstance(val, str):
            valin = ExprHelper.get_expr(val)
            if valin:
                try:
                    ret = await self.runtime.execute(valin, frame.locals)
                except ErrorInAgent:
                    raise
                except Exception as e:
                    if sub_path:
                        message = f"Could not evaluate the Python expression for {path} at {sub_path.removeprefix(".")}: {error_message(e)}"
                    else:
                        message = f"Could not evaluate the Python expression at {path}: {error_message(e)}"
                    raise ShowMessage(message, path=path)
                if TypeChecker.check_type(expected_type, ret):
                    return ret
                else:
                    raise ShowMessage(f"{path!r} is expected to evaluate to {expected_type} but it evaluated to {type(ret).__name__}",
                                      path=path)
            else:
                return val # String literal
        elif isinstance(val, list):
            return [await self.eval_expr(frame, path, item, ExpectedType.anyt, f"{sub_path}.{i}") for i, item in enumerate(val)]
        elif isinstance(val, dict):
            return {k: await self.eval_expr(frame, path, v, ExpectedType.anyt, f"{sub_path}.{k!r}") for k, v in val.items()}
        else:
            return val  # Non string basic value

    def add_output_part(self, val: str | dict | list | LlmResponse):
        parts = self.output.add(val)
        if parts:
            for part in parts:
                self.stream_iter.data(part)

    def check_stop(self) -> None:
        if self.run_ref and self.run_ref.stop_requested:
            raise AgentStopped()

    async def exec_command(self, function: FunctionFrame, command: CommandExecModel, path: str, replay_index: int = -1) -> bool:
        self.check_stop()
        inv = None
        prev_command_ns = self.get_readonly_variable(function, ReadOnlyVariable.command)
        try:
            command_exec = Name2Command.get_command(command.name)
            inv = await self.prepare(function, command, path, replay_index)
            result = await command_exec.exec_command(inv, self)
            if command.name in self._RESULT_PRODUCING_COMMANDS:
                self.set_readonly_variable(function, ReadOnlyVariable.result, result)
            return True
        except FlowControlException:
            raise
        except ErrorFromCloudException as e:
            self.stream_iter.trace(lambda e=e: f"Received an error from Search2o cloud while executing the command {command.qn()}: {e}",
                                   TraceType.error, inv.path if inv else path)
            raise
        except Exception as exc:
            if isinstance(exc, ErrorInAgent):
                if not exc.path:
                    exc.path = inv.path if inv else path
            else:
                self.stream_iter.trace(lambda: f"An unexpected exception was raised executing the command {command.qn()}.",
                                       TraceType.error, inv.path if inv else path)
            self.set_readonly_variable(function, ReadOnlyVariable.exc, exc)
            on_error = command.command_list(AgentWords.onError)
            if on_error:
                try:
                    await self.exec_commands_no_breaks(function, on_error, path)
                except AskException:
                    raise ShowMessage(f"The {CommandName.ask} command cannot be used inside error handling.")
                return False
            else:
                raise
        finally:
            self.set_readonly_variable(function, ReadOnlyVariable.command, prev_command_ns)

    def create_ro(self) -> SimpleNamespace:
        sysvar = SimpleNamespace()
        # Always added
        sysvar.inputs = self.inputs
        sysvar.query = self.query
        sysvar.secret = SecretsManager(self.runtime.secrets_model)

        # Optional
        included = self.runtime.sysvar.sysVariables
        if SysVariables.userEmail in included:
            sysvar.userEmail = self.user_email
        if SysVariables.userSession in included:
            sysvar.userSession = RequestHelper.token_hash(self.request)
        if SysVariables.serverIp in included:
            sysvar.serverIp = Config.init_model.serverIp
        if SysVariables.cookies in included:
            sysvar.cookies = self.request.cookies
        return sysvar

    def create_dict(self) -> dict[str, JsonValue]:
        d = {}
        d[ReadOnlyVariable.sys.value] = self.sysvar
        d[ReadOnlyVariable.agent.value] = self.agent_vars
        d[ReadOnlyVariable.conv.value] = self.conversation_state.conversationVars
        d['__builtins__'] = self.runtime.allowlist.eval_allowlist
        d[ReadOnlyVariable.command.value] = CommandNamespace()
        d[ReadOnlyVariable.env.value] = d # For lookups
        return d

    @staticmethod
    def get_locals_only(d: dict[str, JsonValue]) -> dict[str, JsonValue]:
        predefined = {ro.value for ro in ReadOnlyVariable if ro != ReadOnlyVariable.result} | {'__builtins__'}
        return {
            k:v for k, v in d.items() if k not in predefined
        }

    async def exec_commands_no_breaks(self, function: FunctionFrame, command_list: CommandList, path: str, replay_index: int = -1) -> bool:
        if command_list:
            path = f"{path}.{command_list.name}"
            replay_node = self.get_node(replay_index, CommandListNode)
            start = 0
            if replay_node:
                start = replay_node.commandNumber
                replay_index += 1
            li = command_list.commands[start:]
            for index, command in enumerate(li, start):
                try:
                    await self.exec_command(function, command, path, replay_index)
                except AskException as ae:
                    ae.append(CommandListNode(commandNumber=index))
                    raise
                replay_index = -1
        return True

    async def exec_command_list(self, function: FunctionFrame, command_list: CommandList, path: str, replay_index: int = -1) -> bool:
        if command_list:
            path = f"{path}.{command_list.name}"
            replay_node = self.get_node(replay_index, CommandListNode)
            start = 0
            if replay_node:
                start = replay_node.commandNumber
                replay_index += 1
            li = command_list.commands[start:]
            index = 0
            for index, command in enumerate(li, start):
                try:
                    await self.exec_command(function, command, path, replay_index)
                except BreakException:
                    return False
                except ContinueException:
                    return True
                except AskException as ae:
                    ae.append(CommandListNode(commandNumber=index))
                    raise
                replay_index = -1
        return True

    def get_node[T: Node](
            self,
            replay_index: int,
            expected_type: type[T],
    ) -> T | None:
        if replay_index >= 0:
            if len(self.prev_state) <= replay_index:
                raise ShowMessage("Missing information in accepting user's responses.")
            node = self.prev_state[replay_index]
            if not isinstance(node, expected_type):
                raise ShowMessage("Unexpected type error in accepting user's responses.")
            return cast(T, node)
        return None

    async def exec_function(self, function_name: str, arg_values: dict[str, JsonValue] = None, replay_index: int = -1) -> Any:
        replay_node = self.get_node(replay_index, FunctionNode)
        if replay_node:
            function_name = replay_node.name
            arg_values = replay_node.args
            replay_index += 1
        self.stream_iter.trace(lambda: f"Executing function {str(function_name)!r}", TraceType.flow, function_name)
        function = self.agent.functions.get(function_name)
        if function:
            if not function.commands:
                return None
            path_here = _calling_path.get()
            if function_name in path_here:
                raise ShowMessage(f"Function '{function_name}' is already executing and is being called again (reentrant)")
            path_token = _calling_path.set(path_here | {function_name})
            frame = FunctionFrame(function, self.create_dict())
            path = function_name
            try:
                if function.args:
                    for arg_name, _arg in function.args.items():
                        val = arg_values.get(arg_name) if arg_values else None
                        self.set_variable_val(frame, arg_name, val)
                if replay_node:
                    frame.locals.update(replay_node.localVars)
                try:
                    await self.exec_commands_no_breaks(frame, function.commands, path, replay_index)
                except ReturnFunctionException as e:
                    return e.return_value
                return None
            except AskException as ae:
                ae.append(FunctionNode(name=function_name, args=arg_values if arg_values else {},
                                       localVars=self.get_locals_only(frame.locals)))
                raise
            except (ErrorFromCloudException, AgentDone, FailCommandException, AgentStopped):
                raise
            except Exception as e:
                if function.onError:
                    try:
                        self.set_readonly_variable(frame, ReadOnlyVariable.exc, e)
                        await self.exec_commands_no_breaks(frame, function.onError, path)
                    except ReturnFunctionException as e:
                        return e.return_value
                    except AskException:
                        raise ShowMessage(f"The {CommandName.ask} command cannot be used inside error handling.")
                    except Exception:
                        raise
                else:
                    raise
            finally:
                _calling_path.reset(path_token)
        else:
            raise ShowMessage(f"Unknown function: {function_name!r}")


    async def exec_agent(self, caller_state: list[Node] | None = None) -> ExecResponse:
        self.stream_iter.trace(lambda: f"Starting executing agent {self.agent_name!r}", TraceType.flow)
        agent_path_token = _calling_path.set(frozenset())
        try:
            if caller_state:
                self.prev_state = caller_state
            ret = await self.exec_function(AgentWords.main, None, 0 if self.prev_state else -1)
            return ExecResponse(result_code=AgentExecResult.success, output=self.output, agent_return=ret)
        except ErrorFromCloudException as e:
            if e.status_code == 401:
                self.stream_iter.progress("User session has expired. Must login.")
                return ExecResponse(result_code=AgentExecResult.mustLogin, error_message=e.detail, platform_error=e)
            else:
                return ExecResponse(result_code=AgentExecResult.callFailed, error_message=e.detail, platform_error=e)
        except AgentDone:
            return ExecResponse(result_code=AgentExecResult.success, output=self.output)
        except AgentStopped:
            return ExecResponse(result_code=AgentExecResult.stopped, output=self.output,
                                error_message="The agent was stopped.")
        except AskException as e:
            self.callstack = e.nodes[::-1]
            return ExecResponse(result_code=AgentExecResult.ask, output=self.output, ask_input=e.ask_input)
        except FailCommandException as e:
            return ExecResponse(result_code=AgentExecResult.failCommand, error_message=e.message,
                                user_message=e.message, path=e.path)
        except InvokedAgentFailed as e:
            return ExecResponse(result_code=AgentExecResult.failCommand, error_message=f"{e}",
                                user_message=e.user_message(), path=e.path)
        except ErrorInAgent as e:
            return ExecResponse(result_code=AgentExecResult.errorInAgent, error_message=f"{e}",
                                user_message=e.user_message(), path=e.path)
        except Exception as exc:
            message = f"Unexpected error executing the agent: {type(exc).__name__}"
            try:
                await RestCall.report_error(self.request, message, exc)
            except Exception:
                pass
            return ExecResponse(result_code=AgentExecResult.unexpected, error_message=message)
        finally:
            _calling_path.reset(agent_path_token)
            for mcp in self.mcps.values():
                try:
                    await mcp.close()
                except Exception as e:
                    self.stream_iter.trace(lambda e=e: f"Error closing MCP connection: {e}", TraceType.error)

