# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from typing import Annotated, Self, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from search2o.common.exceptions import ShowMessage
from search2o.execution.agent_state import AgentOutput
from search2o.models.schemaobjects import AgentType, AskInputsModel, ValidationResult


AgentTitle = Annotated[str, Field(max_length=80)]
ConvId = Annotated[str, Field(pattern=r"^[0-9A-Za-z]{22}$")]


_SEARCH_QUERY_MAX_WORDS = 200


def _within_word_limit(value: str) -> str:
    if len(value.split()) > _SEARCH_QUERY_MAX_WORDS:
        raise ShowMessage(f"Query must be at most {_SEARCH_QUERY_MAX_WORDS} words.")
    return value


SearchQuery = Annotated[str, Field(min_length=8, max_length=1000), AfterValidator(_within_word_limit)]

_CLOUD_SEARCH_QUERY_MAX = 500

SearchText = Annotated[str, Field(min_length=8, max_length=10000)]


def cloud_search_query(query: str) -> str:
    if len(query) <= _CLOUD_SEARCH_QUERY_MAX:
        return query
    return query[:_CLOUD_SEARCH_QUERY_MAX]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyRequestModel(RequestModel):
    ...


class PagedRequestModel(RequestModel):
    nextCursor: str | None = Field(default=None, description="Opaque cursor from a prior response's nextCursor. Omit or null to fetch the first page.", title="Next cursor")
    limit: int | None = Field(default=10, description="The maximum number of results to return.", title="Limit")


class ReportWindow(RequestModel):
    start: int = Field(..., description="Start of the window, in epoch milliseconds.", json_schema_extra={"format": "int64"}, title="Window start")
    end: int = Field(..., description="End of the window, in epoch milliseconds.", json_schema_extra={"format": "int64"}, title="Window end")

    @model_validator(mode="after")
    def _window_is_ordered(self) -> Self:
        if self.start > self.end:
            raise ShowMessage("end must not be earlier than start.")
        return self

class ErrorResponseModel(BaseModel):
    message: str = Field(..., title="Error message", description="What went wrong, written to be displayed in the UI.")
    cause: str | None = Field(default=None, exclude_if=lambda value: value is None, title="Cause", description="The name of the underlying error, when the failure was caused by another one.")
    data: dict[str, Any] = Field(default_factory=dict, title="Error data", description="Structured details about the error, when there are any.")

class BaseResponseModel(BaseModel):
    success: bool = Field(default=True, description="Included in every response. Specifies whether the request was successful.", title="Success")
    error: ErrorResponseModel | None = Field(default=None, exclude_if=lambda value: value is None,
                                             title="Error", description="Included in the response if the request was unsuccessful.")


class DraftResponseModel(BaseResponseModel):
    draftid: str = Field(..., description="Unique identifier of the draft within this account, for this user. For a draft of an existing agent this is the agent name.", title="Draft id")
    draftName: str = Field(default="", description="Name the agent will take when this draft is published. Empty on a new draft until the developer names it; on a draft of an existing agent this is that agent's name.", title="Draft name")
    agentTitle: str = Field(default="", description="The title the agent will have when this draft is published.", title="Agent title")
    agentTag: str = Field(default="", title="Agent tag", description="Agent tag used to filter searches.")
    draftUpdatedAt: int = Field(default=0, description="Last time the draft was updated in epoch milliseconds.", json_schema_extra={"format": "int64"}, title="Updated at")
    agentDefinition: AgentType | None = Field(default=None, description="The agent definition, as JSON.", title="Agent definition")
    draftAgentHasChanged: bool = Field(default=False, description="Whether the agent has been published by another user, after this draft was created (changes should be merged before the draft can be published).", title="Agent has changed")
    validationQuery: str | None = Field(default=None, description="The query the draft is run against to validate it.", title="Validation query")
    draftCompilationValidated: bool = Field(default=False, description="Whether the draft definition compiles and passed the security checks.", title="Compilation validated")
    draftExecutionValidated: bool = Field(default=False, description="Whether the draft ran successfully against its validation query. Both this and draftCompilationValidated must be true before the draft can be published.", title="Execution validated")
    isNewDraft: bool = Field(default=False, description="Whether this draft is for a new agent rather than an existing one.", title="New draft")


class ExecAgentResponseModel(BaseResponseModel):
    convid: str | None = Field(default=None, description="Identifier of this conversation. Send it back to continue with the same agent.", title="Conversation id")
    agentName: str | None = Field(default=None, description="The name of the agent that was executed.", title="Agent name")
    output: AgentOutput | None = Field(default=None, description="The agent's output. Set only when the agent was called without streaming.", title="Output")
    resultCode: str = Field(default="", description="How the agent run ended.", title="Result code")
    askInput: AskInputsModel | None = Field(default=None, description="Set when the agent paused to ask the user for input. Send the answers as the inputs of the next call on this conversation.", title="Requested input")

class ValidateDraftResponseModel(ExecAgentResponseModel):
    draftid: str = Field(..., description="The draft that was validated.", title="Draft id")
    validationSuccess: bool = Field(False, description="Whether the draft passed validation and can be published.", title="Validation succeeded")
    validationErrors: list[ValidationResult] = Field(default_factory=list, description="What stopped the draft validating, each with the path of the command or field it was found at. Compile errors come first; a secret or allowlist item the agent server could not find keeps its own type so the right configuration page can be pointed at.", title="Validation errors")
    runtimeError: str | None = Field(default=None, description="The error that ended the validation run, if it failed.", title="Runtime error")
