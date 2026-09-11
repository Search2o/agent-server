# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from enum import StrEnum, auto
from typing import Literal, Annotated

from pydantic import BaseModel, Field, field_validator, StringConstraints

AgentType = str

SafeStr = Annotated[
    str,
    StringConstraints(pattern=r"^(?:\s*(?:[^{\s][\s\S]*)?|[\s\S]*[^\s}]\s*)$"),
    Field(max_length=100),
]

maxMemoryLabelsPerAgent = 10


class CommandName(StrEnum):
    api = auto()
    db = auto()

    prompt = auto()
    llm = auto()
    memory = auto()

    ask = auto()
    search = auto()
    invoke = auto()
    parallel = auto() # Runs several functions concurrently

    func = auto()
    ifv = "if"
    whilev = "while"
    forv = "for"
    breakv = "break" # Break from the innermost loop. If outside loops, goes to the end of current list of commands.
    continuev = "continue" # Continue to the next iteration of the innermost loop. If outside loops, goes to the end of current list of commands.
    returnv = "return" # End this task and return a value

    progress = auto() # Include a progress element to the agent execution result stream
    trace = auto() # Include a trace element to the agent execution result stream
    log = auto() # Log from the agent server. These are not sent to the Search2o cloud.
    output = auto() # When set, this value is used as the agent's output. Otherwise, the value returned by 'main' task is used. Setting this does not change the control flow.

    end = auto() # Ends the agent successfully, saving its state
    fail = auto() # Ends the agent with a failure message, and state is not saved

    var = auto() # Sets variables


class ReadOnlyVariable(StrEnum):
    command = auto()
    result = auto()
    exc = auto()
    env = auto()
    sys = auto()
    agent = auto()
    conv = auto()


class VarNamespace(StrEnum):
    local = auto()
    agent = auto()
    conv = auto()

class ThemeType(StrEnum):
    light = auto()
    dark = auto()
    system = auto()

class UiPrefModel(BaseModel):
    theme: ThemeType = Field(default=ThemeType.system, title="Theme", description="The color scheme of the UI.")
    lang: str = Field(default="en", title="Language", description="The language of the UI. Only English is supported today.")

class ServiceLevel(StrEnum):
    individual = "individual"
    evaluation = "evaluation"
    team = "team"


class UserRole(StrEnum):
    user = auto()
    developer = auto()
    admin = auto()
    owner = auto()

class UserRoleFacet(StrEnum):
    user = auto()
    developer = auto()
    admin = auto()
    owner = auto()
    all = auto()

class DescriptorModel(BaseModel):
    description: str = Field(default="", title="Agent description",
                             description="What this agent does. This determines how well an agent matches a search query entered by the user. If this is empty, the agent will not be matched to any query.",
                            max_length=5000)

class SearchHistoryModel(BaseModel):
    convid: str = Field(..., title="Conversation id", description="Identifier of this conversation.")
    title: str = Field(..., title="Title", description="The conversation's title. By default this is the first query in it.")
    lastExecuted: int | None = Field(..., title="Last executed", description="When the conversation was last run, in epoch milliseconds.", json_schema_extra={"format": "int64"})
    pinned: bool = Field(default=False, title="Pinned", description="Whether the user has pinned this conversation.")

class AgentTitleModel(BaseModel):
    agentName: str = Field(..., title="Agent name", description="The name that identifies the agent.")
    agentTitle: str = Field(..., title="Agent title", description="The agent's title, shown to users.")

class ValidationResultType(StrEnum):
    error = "error"
    secret = "secret"
    allowlistItem = "allowlistItem"


class ValidationResult(BaseModel):
    vtype: ValidationResultType
    path: str = ""
    detail: str


class ValidationResults(BaseModel):
    results: list[ValidationResult] = Field(default_factory=list)


class DraftTemplateModel(BaseModel):
    name: str = Field(..., title="Template name", description="The name of the draft template.")
    description: str = Field(..., title="Description", description="What the template is for.")


class TextPartApi(BaseModel):
    contentType: Literal["text"] = Field(default="text", title="Content type", description="Identifies this part as text.")
    text: str = Field(..., title="Text", description="The text of this part, treated as markdown.")


class HtmlPartApi(BaseModel):
    contentType: Literal["html"] = Field(default="html", title="Content type", description="Identifies this part as HTML.")
    text: str = Field(..., title="HTML", description="The HTML of this part.")


class ImagePartApi(BaseModel):
    contentType: Literal["image"] = Field(default="image", title="Content type", description="Identifies this part as an image.")
    text: str = Field(..., title="Image data", description="The image, base64 encoded.")
    mimeType: str = Field(default="", title="MIME type", description="The image's MIME type, such as image/png.")

type ContentPartApi = Annotated[TextPartApi | HtmlPartApi | ImagePartApi, Field(discriminator="contentType")]

TYPE_EXPR_PATTERN = (
    r"^(?:"
    r"(?:str|int|float|bool|null|any)"                                  # primitives
    r"|list\[(?:[^\[\]]+)\]"                                            # list[T]
    r"|dict\[(?:str|int)\s*,\s*(?:[^\[\]]+)\]"                          # dict[K,V] (K usually str)
    r")"
    r"(?:\s*\|\s*(?:str|int|float|bool|null|any|list\[(?:[^\[\]]+)\]|dict\[(?:str|int)\s*,\s*(?:[^\[\]]+)\]))*$"
)


class FunctionArgModel(BaseModel):
    type: str = Field(
        default="str",
        title="Argument type",
        description=(
            "Type expression for JSON Schema generation. Supported: "
            "primitives (str, int, float, bool, null, any), "
            "containers (list[T], dict[str,V]), and unions (T1 | T2). "
            "Examples: str, int|null, list[str], dict[str, any], list[int|str]."
        ),
        pattern=TYPE_EXPR_PATTERN,
    )
    description: str = Field(default="", title="Description", description="Description of this argument, which is needed only when used in tool calling. Include all the constraints of this argument here for the LLM.")
    required: bool = Field(default=True, title="Required", description="Whether the argument is required. This only tells the LLM; an argument that is not passed in is set to None.")

class AgentFunctionModel(BaseModel):
    name: str = Field(..., title="Function name", description="The name the LLM uses to call this function.")
    description: str = Field(..., title="Description", description="What the function does, written for the LLM.")
    parameters: dict[str, FunctionArgModel] = Field(default_factory=dict, title="Parameters", description="The function's arguments, keyed by name.")

_RESERVED_INPUT_NAMES = {"query"}

class AskInputModel(BaseModel):
    name: SafeStr = Field(..., title="Input name", description="The name of the input. The user's answer is returned under this name.", max_length=50,
                      pattern=r"^[A-Za-z][A-Za-z0-9_]*[A-Za-z0-9]$", )
    type: Literal["str", "password", "text", "chooseOne", "chooseMany"] = Field(default="str", title="Input type", description="The kind of input control to show.")
    label: SafeStr | None = Field(default=None, title="Label", description="The label shown next to the input.", max_length=30)
    description: SafeStr = Field(default="", title="Input description", description="Help text shown to the user under the input.", max_length=80)
    options: list[SafeStr] = Field(default_factory=list, title="Options", description="The values the user chooses from, for chooseOne and chooseMany.")
    default: SafeStr | None = Field(default=None, title="Default value", description="The value the input starts with.")
    hidden: bool = Field(default=False, title="Hidden", description="Sent back from the UI without being shown to the user.")

    @field_validator("name")
    @classmethod
    def name_not_reserved(cls, value: str) -> str:
        if value in _RESERVED_INPUT_NAMES:
            raise ValueError(f"Ask command's inputs' name cannot be '{value}'")
        return value

class AskInputsModel(BaseModel):
    message: str = Field(default="Please provide these inputs", title="Ask message", description="Message shown above the input fields.")
    inputs: list[AskInputModel] = Field(default_factory=list, title="Inputs", description="The inputs the user is asked for.")

class AgentExecResult(StrEnum):
    success = "success" # Agent completed successfully (Not included in error report)
    ask = "ask" # Agent ended in a ask command (Not included in error report)
    callFailed = "callFailed" # Call to an external system failed
    failCommand = "failCommand" # Agent ended with a fail command
    errorInAgent = "errorInAgent" # Agent has some coding error
    unknownConversation = "unknownConversation" # Conversation is unknown or expired, or it is paused on an ask by a different agent
    timedOut = "timedOut" # Agent timed out, based on the max agent runtime setting
    stopped = "stopped" # User cancelled the agent execution
    mustLogin = "mustLogin" # Session timed out in the middle of an agent execution
    unexpected = "unexpected" # An unknown exception was raised in the agent


class ConnectStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    denied = "denied"
    expired = "expired"


class NotificationType(StrEnum):
    agentIndexed = "agentIndexed"
    indexingSubmitted = "indexingSubmitted"
    indexingFailed = "indexingFailed"
    descriptorDeleted = "descriptorDeleted"
    tagUpdated = "tagUpdated"
    titleUpdated = "titleUpdated"
    unknownPasswordReset = "unknownPasswordReset"
    servers = auto()
    encryption = auto()
    secrets = auto()
    auth = auto()
    operators = auto()
    validation = auto()
    allowlist = auto()
    sysvar = auto()
    search = auto()
    apiConnectionPools = "apiConnectionPools"
    llm = auto()
    api = auto()
    mcp = auto()
    db = auto()
    prompt = auto()
