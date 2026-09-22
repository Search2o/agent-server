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

class GrantedNames:
    def __init__(self, path: str) -> None:
        self._path = path

    def _grant(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)

    def __getattr__(self, name: str) -> Any:
        path = object.__getattribute__(self, "_path")
        raise AttributeError(f"'{path}.{name}' is not in the Allowlist.")

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        path = object.__getattribute__(self, "_path")
        raise TypeError(f"'{path}' is not in the Allowlist: only what is listed under it can be used.")

    def __repr__(self) -> str:
        granted = sorted(n for n in vars(self) if not n.startswith("_"))
        return f"<{self._path}: {', '.join(granted)}>"

class Allowlist:

    def __init__(self, ew: EvalAllowlistModel):
        self.errors: dict[str, str] = {}
        self.ew = ew
        self.llm_adapters = []

        mutable: dict[str, _ImportedObject] = self.build_eval_allowlist(self.ew.allowlist)
        self.eval_allowlist: types.MappingProxyType[str, _ImportedObject] = types.MappingProxyType(mutable)
        self.check_llm_adapters()

    def resolve(self, spec: str, builtin_classes: set[str], line: str = "") -> tuple[str, _ImportedObject] | None:
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
                    try:
                        symbol = getattr(module, symbol_name)
                    except AttributeError:
                        symbol = importlib.import_module(path)
                    found = True

            if found:
                return alias.strip(), symbol
        except Exception:
            self.errors[line or spec] = "Could not be imported."
        return None


    def resolve_function(self, name: str) -> _ImportedObject | None:
        ret = self.resolve(name, self.builtin_classes())
        return ret[1] if ret else None


    def strip_comment(self, line: str) -> str:
        i = line.find("#")
        return (line if i == -1 else line[:i]).rstrip()


    def build_eval_allowlist(self, functions: list[str]) -> dict:
        env: dict[str, _ImportedObject] = {}
        bc = self.builtin_classes()
        for spec in functions:
            line = self.strip_comment(spec).strip()
            if not line:
                continue
            path, _, alias = (part.strip() for part in line.partition(" as "))
            parts = path.split(".")
            if parts[-1] == "*":
                if alias:
                    self.errors[spec] = "A star import cannot be renamed with 'as'."
                else:
                    self.star_import(env, path, parts[:-1], spec)
            elif len(parts) == 1 and not hasattr(builtins, parts[0]):
                module = self.import_module(path, spec)
                if module is not None:
                    env[alias or path] = self.granted_module(alias or path, module)
            elif alias or len(parts) == 1:
                ret = self.resolve(line, bc, spec)
                if ret:
                    env[ret[0]] = self.contain(ret[0], ret[1])
            else:
                ret = self.resolve(path, bc, spec)
                if ret:
                    self.graft(env, parts, ret[1])
        return env

    def contain(self, label: str, obj: _ImportedObject) -> _ImportedObject:
        return self.granted_module(label, obj) if isinstance(obj, ModuleType) else obj

    def granted_module(self, label: str, module: ModuleType) -> GrantedNames:
        holder = GrantedNames(label)
        for name in dir(module):
            if name.startswith("_"):
                continue
            try:
                value = getattr(module, name)
            except Exception:
                continue
            if isinstance(value, ModuleType):
                continue
            holder._grant(name, value)
        return holder

    def import_module(self, path: str, line: str = "") -> ModuleType | None:
        try:
            return importlib.import_module(path)
        except Exception:
            self.errors[line or path] = "Could not be imported."
            return None

    def star_import(self, env: dict, path: str, parts: list[str], line: str = "") -> None:
        module = self.import_module(".".join(parts), line) if parts else None
        if module is None:
            if parts:
                return
            self.errors[line or path] = "Could not be imported."
            return
        names = getattr(module, "__all__", None) or [n for n in dir(module) if not n.startswith("_")]
        for name in names:
            try:
                value = getattr(module, name)
            except Exception:
                continue
            if not isinstance(value, ModuleType):
                env[name] = value

    def graft(self, env: dict, parts: list[str], symbol: _ImportedObject) -> None:
        root = parts[0]
        holder = env.get(root)
        if not isinstance(holder, GrantedNames):
            if isinstance(holder, (ModuleType, type)):
                return
            holder = GrantedNames(root)
            env[root] = holder
        for step in parts[1:-1]:
            nxt = getattr(holder, step, None)
            if not isinstance(nxt, GrantedNames):
                nxt = GrantedNames(f"{holder._path}.{step}")
                holder._grant(step, nxt)
            holder = nxt
        holder._grant(parts[-1], self.contain(".".join(parts), symbol))

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
        for name, cl in self.eval_allowlist.items():
            if inspect.isclass(cl) and issubclass(cl, LlmAdapter):
                try:
                    obj = cl() # Assumes a no-arg constructor
                    self.llm_adapters.append(obj)
                except Exception as e:
                    self.errors[name] = f"This is a subclass of LlmAdapter, but produces errors while instantiating with a default constructor: {e}"
