# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio
import json
import types
from typing import Any, ClassVar, TypeVar
from collections.abc import Awaitable

from fastapi import Request
from pydantic import BaseModel

from search2o.common.closable import Closable
from search2o.common.exceptions import ShowMessage, InitializationError, error_message
from search2o.common.mylogger import MyLogger
from search2o.database.db import Database
from search2o.execution.agentexec import AgentExec
from search2o.common.sensitivestring import SensitiveString
from search2o.execution.allowlist import Allowlist
from search2o.execution.encryptor import Encryptor
from search2o.execution.network import Network
from search2o.llm.llmcontext import AllLlmContexts
from search2o.models.configtypes import AuthMethod, SystemConfigPart, AgentConfigPart
from search2o.models.systemconfig import SearchOptionsModel, AgentValidationModel, ApiServerModel, DbConnectionModel, \
    McpServerModel, PromptProfileModel, AgentRuntime, \
    LlmModel, NamedBaseModel, AgentSecretsModel, EncryptionModel, \
    SecretSource, AgentConfigModelUnion, ApiConnectionPoolsModel, SysVar

C = TypeVar("C", bound=BaseModel)
T = TypeVar("T", bound=NamedBaseModel)


PROMPT_DECRYPTION_ERROR = "Decryption error"


class RuntimeState:
    _compiledExpr: dict[str, types.CodeType] = {}

    def __init__(self):
        self.retired: list[Closable] = []

        self.config_update_at: int
        self.search_options: SearchOptionsModel
        self.validation: AgentValidationModel
        self.secrets_model: AgentSecretsModel
        self.encryption_model: EncryptionModel
        self.allowlist: Allowlist
        self.sysvar: SysVar

        self.apis: dict[str, ApiServerModel]
        self.db_service: dict[str, DbConnectionModel]
        self.llm_options: dict[str, LlmModel]
        self.mcp_servers: dict[str, McpServerModel]
        self.prompts: dict[str, PromptProfileModel]

        self.network: Network | None = None
        self.db_connections: Database | None = None
        self.llm_connections: AllLlmContexts | None = None


    async def update(self, request: Request, ar: AgentRuntime, prev: RuntimeState):
        self.config_update_at = ar.updated

        self.search_options = self._d2m(ar, SystemConfigPart.search) if SystemConfigPart.search in ar.updatedSystemConfigs else prev.search_options
        self.validation = self._d2m(ar, SystemConfigPart.validation) if SystemConfigPart.validation in ar.updatedSystemConfigs else prev.validation
        self.encryption_model = self._d2m(ar, SystemConfigPart.encryption) if SystemConfigPart.encryption in ar.updatedSystemConfigs else prev.encryption_model
        self.sysvar = self._d2m(ar, SystemConfigPart.sysvar) if SystemConfigPart.sysvar in ar.updatedSystemConfigs else prev.sysvar
        self.prompts = self._l2d(ar, AgentConfigPart.prompt) if AgentConfigPart.prompt in ar.updatedAgentConfigs else prev.prompts
        self.mcp_servers = self._l2d(ar, AgentConfigPart.mcp) if AgentConfigPart.mcp in ar.updatedAgentConfigs else prev.mcp_servers

        # Build the allowlist BEFORE decrypting hosted secrets: client-encrypted
        new_allowlist_model = self._d2m(ar, SystemConfigPart.allowlist)
        self.allowlist = Allowlist(new_allowlist_model) if new_allowlist_model is not None else prev.allowlist

        if AgentConfigPart.prompt in ar.updatedAgentConfigs:
            for profile in self.prompts.values():
                for field in ("system", "user"):
                    text = getattr(profile, field)
                    if text:
                        try:
                            setattr(profile, field, await Encryptor.decrypt(request, self, text))
                        except Exception as e:
                            MyLogger.error(f"Could not decrypt the {field} prompt of profile {profile.name!r}: {SensitiveString.safe_text(error_message(e))}")
                            setattr(profile, field, PROMPT_DECRYPTION_ERROR)

        if SystemConfigPart.secrets in ar.updatedSystemConfigs:
            self.secrets_model = self._d2m(ar, SystemConfigPart.secrets)
            if self.secrets_model.secretSource == SecretSource.hosted and self.secrets_model.secretsEncrypted:
                self.secrets_model.cache = json.loads(await Encryptor.decrypt(request, self,self.secrets_model.secretsEncrypted))
        else:
            self.secrets_model = prev.secrets_model

        if SystemConfigPart.apiConnectionPools in ar.updatedSystemConfigs:
            api_connection_pools: ApiConnectionPoolsModel = self._d2m(ar, SystemConfigPart.apiConnectionPools)
            self.network = Network(api_connection_pools)
            self._retire(prev.network)
        else:
            self.network = prev.network

        new_apis = self._l2d(ar, AgentConfigPart.api)
        self.apis = new_apis if new_apis is not None else prev.apis

        new_dbs = self._l2d(ar, AgentConfigPart.db)
        self.db_service = new_dbs if new_dbs is not None else prev.db_service

        if new_dbs is not None:
            self.db_connections = Database(self.validation)
            self._retire(prev.db_connections)
        else:
            self.db_connections = prev.db_connections
            self.db_connections.validation = self.validation

        new_llm_options = self._l2d(ar, AgentConfigPart.llm)
        self.llm_options = new_llm_options if new_llm_options is not None else prev.llm_options
        if new_llm_options is not None or new_allowlist_model is not None:
            self.llm_connections = AllLlmContexts(self.llm_options, self.allowlist.llm_adapters)
        else:
            self.llm_connections = prev.llm_connections

    def _retire(self, closable: Closable | None):
        if closable is not None:
            self.retired.append(closable)

    def in_use(self) -> list[Closable]:
        return [c for c in (self.network, self.db_connections) if c is not None]

    def start(self, convid: str):
        Runtime.agent_started(convid)

    def done(self, convid: str):
        Runtime.agent_done(convid)

    @staticmethod
    async def execute_expr(ce: str | types.CodeType, d: dict) -> Any:
        exec(ce, d)
        value_name = "_tmp_value_"
        if value_name not in d:
            raise ShowMessage("Unexpected internal error in evaluating an expression.")
        ret = d[value_name]
        d.pop(value_name, None)
        if isinstance(ret, Awaitable):
            ret = await ret
        return ret

    @classmethod
    async def execute(cls, expr: str, d: dict) -> Any:
        ce = cls._compiledExpr.get(expr)
        if not ce:
            ce = compile(expr, "<string>", "exec")
            cls._compiledExpr[expr] = ce
        return await cls.execute_expr(ce, d)

    @staticmethod
    def _d2m(ar: AgentRuntime, part: SystemConfigPart) -> C | None:
        return ar.updatedSystemConfigs.get(part)

    @staticmethod
    def _l2d(ar: AgentRuntime, part: AgentConfigPart) -> dict[str, T] | None:
        items: list[AgentConfigModelUnion] = ar.updatedAgentConfigs.get(part)
        if items is not None:
            result: dict[str, T] = {}
            for model in items:
                result[model.name] = model
            return result
        else:
            return None


class Runtime:
    _current: RuntimeState = RuntimeState()
    password_help: ClassVar[str] = ""
    auth_method: ClassVar[AuthMethod] = AuthMethod.builtin
    _update_lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _bg_tasks: ClassVar[set[asyncio.Task]] = set()
    _running: ClassVar[dict[str, int]] = {}
    _pending: ClassVar[list[tuple[list[Closable], set[str]]]] = []

    @classmethod
    def track_task(cls, task: asyncio.Task) -> asyncio.Task:
        cls._bg_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            cls._bg_tasks.discard(t)
            if not t.cancelled() and t.exception() is not None:
                MyLogger.warning(f"Background task failed: {t.exception()}")

        task.add_done_callback(_done)
        return task

    @classmethod
    async def start_agent_exec(cls, request: Request, config_update_at: int, convid: str) -> RuntimeState:
        current: RuntimeState = cls._current

        if current.config_update_at is None or current.config_update_at < config_update_at:
            async with cls._update_lock:
                current = cls._current
                if current.config_update_at is None or current.config_update_at < config_update_at:
                    await cls.update(request, current.config_update_at if current.config_update_at is not None else 0)
                    current = cls._current

        current.start(convid)
        return current

    @classmethod
    def agent_started(cls, convid: str) -> None:
        cls._running[convid] = cls._running.get(convid, 0) + 1

    @classmethod
    def agent_done(cls, convid: str) -> None:
        running = cls._running.get(convid, 0) - 1
        if running > 0:
            cls._running[convid] = running
            return
        cls._running.pop(convid, None)
        pending: list[tuple[list[Closable], set[str]]] = []
        for closables, waiting in cls._pending:
            waiting.discard(convid)
            if waiting:
                pending.append((closables, waiting))
            else:
                cls.track_task(asyncio.create_task(cls._close(closables)))
        cls._pending = pending

    @classmethod
    def retire(cls, closables: list[Closable]) -> None:
        if not closables:
            return
        waiting = set(cls._running)
        if waiting:
            cls._pending.append((closables, waiting))
        else:
            cls.track_task(asyncio.create_task(cls._close(closables)))

    @staticmethod
    async def _close(closables: list[Closable]) -> None:
        for closable in closables:
            try:
                await closable.close()
            except Exception as e:
                MyLogger.warning(f"Error closing {type(closable).__name__}: {e}")

    @classmethod
    async def update(cls, request: Request | None = None, update_at: int = 0):
        from search2o.common.rest_call import RestCall
        rt0 = (await RestCall.call_method(request, "getRuntime", {"lastUpdatedAt": update_at})).get("runtime")
        rt = AgentRuntime.model_validate(rt0)
        cls.password_help = rt.passwordHelp
        cls.auth_method = rt.authMethod
        cls._remove_stale_agents(rt.agentVersions)
        if update_at == 0:
            cls.initial_update_check(rt)
        state = RuntimeState()
        await state.update(request, rt, cls._current)
        cls._current = state
        cls.retire(state.retired)
        RestCall.set_network(state.network)
        MyLogger.info("Agent runtime updated.")

    _agents: ClassVar[dict[str, AgentExec]] = {}
    _agents_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def get_agent(cls, request: Request, name: str) -> AgentExec:
        from search2o.common.rest_call import RestCall
        async with cls._agents_lock:
            agent = cls._agents.get(name)
            if not agent:
                obj = await RestCall.call_method(request, "getAgentForExecution", {"agentName": name})
                agent = AgentExec(obj.get("agentName"), obj.get("agentTitle"),
                                  obj.get("agentVersion"), obj.get("agentDefinition"))
                cls._agents[name] = agent
            return agent

    @classmethod
    def _remove_stale_agents(cls, agent_versions: dict[str, int]) -> None:
        for name, version in agent_versions.items():
            agent = cls._agents.get(name)
            if agent and agent.agent_version != version:
                cls._agents.pop(name, None)

    @classmethod
    def current(cls):
        return cls._current


    @classmethod
    def initial_update_check(cls, ar: AgentRuntime):
        error = False
        for p in (SystemConfigPart.allowlist, SystemConfigPart.sysvar, SystemConfigPart.search, SystemConfigPart.validation, SystemConfigPart.apiConnectionPools):
            if p not in ar.updatedSystemConfigs:
                error = True
        for p in AgentConfigPart:
            if p not in ar.updatedAgentConfigs:
                error = True
        if error:
            raise InitializationError("Unexpected error in initializing the agent server. Please report.")

    @classmethod
    async def close(cls):
        pending, cls._pending = cls._pending, []
        for closables, _ in pending:
            await cls._close(closables)
        await cls._close(cls._current.in_use())
