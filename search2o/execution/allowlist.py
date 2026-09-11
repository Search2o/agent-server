# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import builtins
import importlib
import inspect
import types
from types import ModuleType
from typing import Any, Union
from collections.abc import Callable

from search2o.llm.llmadapter import LlmAdapter
from search2o.models.systemconfig import EvalAllowlistModel

_ImportedObject = Union[Callable[..., Any], type, ModuleType, Any]

class Allowlist:

    def __init__(self, ew: EvalAllowlistModel):
        self.errors = []
        self.ew = ew
        self.llm_adapters = []
        self.e2e_encrypted = False

        mutable: dict[str, _ImportedObject] = self.build_eval_allowlist(self.ew.allowlist)
        self.eval_allowlist: types.MappingProxyType[str, _ImportedObject] = types.MappingProxyType(mutable)
        self.check_llm_adapters()


    def resolve(self, spec: str, builtin_classes: set[str]) -> tuple[str, _ImportedObject] | None:
        try:
            if ' as ' in spec:
                path, alias = spec.split(' as ')
            else:
                path = alias = spec

            parts = path.strip().split('.')

            symbol = None
            found = False
            if len(parts) == 1:
                symbol = getattr(builtins, parts[0])
                found = True
            elif len(parts) == 2 and parts[0] in builtin_classes:
                symbol = getattr(getattr(builtins, parts[0]), parts[1])
                found = True
            else:
                module_path = '.'.join(parts[:-1])

                symbol_name = parts[-1]
                module = importlib.import_module(module_path)
                if symbol_name != "*":
                    symbol = getattr(module, symbol_name)
                    found = True

            if found:
                return alias.strip(), symbol
        except Exception:
            self.errors.append(f"Error importing '{spec}'")
        return None


    def strip_comment(self, line: str) -> str:
        i = line.find("#")
        return (line if i == -1 else line[:i]).rstrip()


    def build_eval_allowlist(self, functions: list[str]) -> dict:
        env = {}
        bc = self.builtin_classes()
        for spec in functions:
            line = self.strip_comment(spec)
            if line.strip():
                ret = self.resolve(line, bc)
                if ret:
                    alias, symbol = ret
                    env[alias] = symbol
        return env

    def builtin_classes(self) -> set[str]:
        names: list[str] = []
        for name, obj in vars(builtins).items():
            if not isinstance(obj, type):
                continue
            for attr_name in dir(obj):
                if attr_name.startswith("__") and attr_name.endswith("__"):
                    continue
                try:
                    attr: Any = getattr(obj, attr_name)
                except Exception:
                    continue
                if callable(attr):
                    names.append(name)
                    break
        return set(names)

    def check_llm_adapters(self):
        for cl in self.eval_allowlist.values():
            if inspect.isclass(cl) and issubclass(cl, LlmAdapter):
                try:
                    obj = cl() # Assumes a no-arg constructor
                    self.llm_adapters.append(obj)
                except Exception as e:
                    self.errors.append(f"Class {cl.__name__} is a subclass of LlmAdapter, but produces errors while instantiating with a default constructor: {e}")
