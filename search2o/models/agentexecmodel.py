# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from pydantic import JsonValue, BaseModel, Field

from .schemaobjects import FunctionArgModel, CommandName, VarNamespace


class SetVariable(BaseModel):
    ns: VarNamespace = VarNamespace.local
    name: str
    path: list[str | int] | None = None
    value: JsonValue

    def ns_str(self) -> str:
        return f"{self.ns}." if self.ns != VarNamespace.local else ""

    def pn(self):
        path_str = "".join(["[{ }]" if self.is_expr(p) else f"[{p!r}]" for p in self.path]) if self.path else ""
        path = f"{self.ns_str()}{self.name}{path_str}"
        return f"'{path}'" if "." in path else path

    @staticmethod
    def is_expr(index: str | int) -> bool:
        return isinstance(index, str) and index.startswith("{") and index.endswith("}")

class CommandExecModel(BaseModel):
    name: CommandName
    suffix: str = ""
    params: dict[str, JsonValue] = Field(default_factory=dict)
    command_blocks: dict[str, CommandList | None] = Field(default_factory=dict)
    variables: list[SetVariable] | None = Field(default=None)
    scalar_value: JsonValue = None

    def param(self, name: str, default: JsonValue = None) -> JsonValue:
        return self.params[name] if name in self.params else default

    def command_list(self, name: str) -> CommandList:
        return self.command_blocks.get(name)

    def get_vars(self) -> list[SetVariable]:
        return self.variables if self.variables else []

    def qn(self):
        v = f"{self.name}.{self.suffix}" if self.suffix else self.name
        return f"'{v}'"

    def pn(self):
        return f"'{self.name}.{self.suffix}'" if self.suffix else self.name

class CommandList(BaseModel):
    name: str
    commands: list[CommandExecModel] = Field(default_factory=list)

class FunctionExecModel(BaseModel):
    name: str
    description: str | None = None
    args: dict[str, FunctionArgModel] | None = None
    commands: CommandList | None = None
    onError: CommandList | None = Field(default=None)

class AgentExecModel(BaseModel):
    functions: dict[str, FunctionExecModel] = Field(default_factory=dict)

