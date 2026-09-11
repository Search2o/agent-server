# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, Field

from search2o.common.toolresponse import ToolResponse
from search2o.models.prompt import PromptElement


class Node(BaseModel):
    ...

class CommandNode(Node):
    ntype: Literal["command"] = "command"
    commandState: dict[str, Any] = Field(default_factory=dict) # Command specific state that each command would store

class IfCommandNode(CommandNode):
    ntype: Literal["if"] = "if"
    condValue: bool

class InvokeCommandNode(CommandNode):
    ntype: Literal["invoke"] = "invoke"
    inputs: dict[str, Any]
    agent_name: str
    agent_version: int
    share_prompts: bool
    nodes: list[NodeUnion]

class WhileCommandNode(CommandNode):
    ntype: Literal["while"] = "while"
    cnt: int

class AskCommandNode(CommandNode):
    ntype: Literal["ask"] = "ask"

class LlmCommandNode(CommandNode):
    ntype: Literal["llm"] = "llm"
    elements: list[PromptElement]
    systemPrompt: str
    elementCount: int
    toolCallCount: int
    responses: list[ToolResponse]

class FuncCommandNode(CommandNode):
    ntype: Literal["func"] = "func"
    name: str # Name of the function to be called
    args: dict[str, Any] # Function's arguments


class CommandListNode(Node):  # commands, do, then, else
    ntype: Literal["commandlist"] = "commandlist"
    commandNumber: int # Nth command that is being called starting from zero

class FunctionNode(Node): # Any function name
    ntype: Literal["function"] = "function"
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    localVars: dict[str, Any] = Field(default_factory=dict) # Local variables in the function


NodeUnion: TypeAlias = Annotated[
    CommandNode
    | IfCommandNode
    | InvokeCommandNode
    | WhileCommandNode
    | AskCommandNode
    | FuncCommandNode
    | LlmCommandNode
    | CommandListNode
    | FunctionNode,
    Field(discriminator="ntype"),
]

InvokeCommandNode.model_rebuild()
