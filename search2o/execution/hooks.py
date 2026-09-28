# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

import importlib
import inspect
from typing import Any, ClassVar
from collections.abc import Callable

from search2o.common.exceptions import error_message
from search2o.common.flowcontrol import HookRefused
from search2o.common.mylogger import MyLogger
from search2o.llm.llmadapter import LlmAdapter
from search2o.models.configtypes import AgentConfigPart
from search2o.models.systemconfig import HooksModel

_ADAPTERS_FIELD = "llmAdapters"
_VALIDATORS_FIELD = "agentConfigValidators"


class Hooks:
    _functions: ClassVar[dict[str, Callable]] = {}
    llm_adapters: ClassVar[list[LlmAdapter]] = []
    config_validators: ClassVar[dict[AgentConfigPart, Callable]] = {}
    errors: ClassVar[list[str]] = []

    @staticmethod
    def resolve(path: str) -> Any:
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            try:
                obj: Any = importlib.import_module(".".join(parts[:i]))
            except ImportError:
                continue
            for attr in parts[i:]:
                obj = getattr(obj, attr)
            return obj
        raise ImportError(f"No module could be imported from {path!r}")

    @classmethod
    def _function(cls, field: str, path: str) -> Callable | None:
        try:
            obj = cls.resolve(path)
        except Exception as e:
            cls._error(f"Hook {field} ({path}) could not be loaded: {error_message(e)}")
            return None
        if not inspect.iscoroutinefunction(obj):
            cls._error(f"Hook {field} ({path}) is not an async function.")
            return None
        return obj

    @classmethod
    def _adapter(cls, path: str) -> LlmAdapter | None:
        try:
            obj = cls.resolve(path)
        except Exception as e:
            cls._error(f"LLM adapter {path} could not be loaded: {error_message(e)}")
            return None
        if not (inspect.isclass(obj) and issubclass(obj, LlmAdapter)):
            cls._error(f"LLM adapter {path} is not a subclass of LlmAdapter.")
            return None
        try:
            return obj()
        except Exception as e:
            cls._error(f"LLM adapter {path} could not be built with no arguments: {error_message(e)}")
            return None

    @classmethod
    def _error(cls, message: str) -> None:
        cls.errors.append(message)
        MyLogger.error(message)

    @classmethod
    def load(cls, model: HooksModel) -> None:
        cls._functions, cls.llm_adapters, cls.config_validators, cls.errors = {}, [], {}, []
        for field in HooksModel.model_fields:
            value = getattr(model, field)
            if field in ("type", _ADAPTERS_FIELD, _VALIDATORS_FIELD) or value is None:
                continue
            fn = cls._function(field, value)
            if fn is not None:
                cls._functions[field] = fn
        for path in model.llmAdapters:
            adapter = cls._adapter(path)
            if adapter is not None:
                cls.llm_adapters.append(adapter)
        for part, path in model.agentConfigValidators.items():
            fn = cls._function(f"{_VALIDATORS_FIELD}.{part.value}", path)
            if fn is not None:
                cls.config_validators[part] = fn

    @classmethod
    def has(cls, name: str) -> bool:
        return name in cls._functions

    @classmethod
    async def call(cls, name: str, args_fn: Callable[[], dict[str, Any]]) -> Any:
        fn = cls._functions.get(name)
        if fn is None:
            return None
        return await fn(args_fn())

    @classmethod
    async def guard(cls, name: str, args_fn: Callable[[], dict[str, Any]]) -> None:
        try:
            await cls.call(name, args_fn)
        except Exception as e:
            raise HookRefused(error_message(e)) from e

    @classmethod
    async def validate_config(cls, part: AgentConfigPart, args_fn: Callable[[], dict[str, Any]]) -> None:
        fn = cls.config_validators.get(part)
        if fn is not None:
            await fn(args_fn())
