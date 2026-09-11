# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import asyncio
from typing import Annotated, Literal, Self

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field, JsonValue, model_validator
from starlette.responses import StreamingResponse

from search2o.api.admin import api_connection_pool_names
from search2o.api.exec import stop_when_client_leaves
from search2o.common.enums import TraceType
from search2o.common.rest_call import RestCall
from search2o.common.exceptions import ShowMessage
from search2o.common.sensitivestring import SensitiveString
from search2o.execution.agentexec import AgentExec
from search2o.execution.encryptor import Encryptor
from search2o.execution.conversationrun import ConversationRun, ExecStartResponseModel
from search2o.execution.runref import RunRef
from search2o.execution.runtime import Runtime, RuntimeState
from search2o.execution.secretsmanager import SecretsManager
from search2o.execution.streamiter import StreamIter, StreamDraftReturn
from search2o.models.configtypes import AgentName, AgentTag
from search2o.models.apimodels import AgentTitle, BaseResponseModel, ConvId, \
    DraftResponseModel, EmptyRequestModel, PagedRequestModel, ReportWindow, RequestModel, SearchQuery, \
    ValidateDraftResponseModel
from search2o.models.schemaobjects import AgentExecResult, AgentType, DescriptorModel, NotificationType, UserRole, \
    ValidationResult, ValidationResults, ValidationResultType

dev_router = APIRouter(prefix="/api/dev", tags=["dev"])


def _check_definition_length(definition: AgentType | None) -> None:
    if definition and len(definition) > Runtime.current().validation.agentMaxLength:
        raise ShowMessage(f"Agent definition has to be less than {Runtime.current().validation.agentMaxLength} characters, including comments.")


# ----- request models shared by several endpoints -----

_AgentDefinition = Annotated[AgentType, Field(min_length=24, max_length=20480)]


class AgentNameModel(RequestModel):
    agentName: AgentName


class DraftidModel(RequestModel):
    draftid: str


# ----- item / response models owned by this router -----

class DraftItemModel(BaseModel):
    draftid: str = Field(..., title="Draft ID", description="Unique identifier of the draft within this account, for this user. For a draft of an existing agent this is the agent name.")
    draftName: str = Field(default="", title="Name", description="Name the agent will take when this draft is published.")
    agentTitle: str = Field(default="", title="Title", description="Title of the agent (draft)")
    agentTag: str = Field(default="", title="Agent tag", description="Agent tag used to filter searches.")
    draftUpdatedAt: int = Field(default=0, title="Last modified", description="Last time the draft was updated in epoch milliseconds.", json_schema_extra={"format": "int64"})
    isNewDraft: bool = Field(default=False, description="Whether the draft is for a new agent or existing one.")
    draftCompilationValidated: bool = Field(default=False, description="Whether the draft definition compiles and passed the security checks.")
    draftExecutionValidated: bool = Field(default=False, description="Whether the draft ran successfully against its validation query.")


class GetAllDraftsResponseModel(BaseResponseModel):
    drafts: list[DraftItemModel] = Field(..., description="List of agent drafts by this user. Drafts cannot be seen by other users.")
    nextCursor: str | None = Field(default=None, description="Opaque cursor to fetch the next page; pass it back as nextCursor. Null when there are no more results.")


class AgentItemModel(BaseModel):
    agentName: str = Field(..., title="Name", description="Name of the agent.")
    agentTitle: str = Field(..., title="Title", description="Title of the agent.")
    agentTag: str = Field(..., title="Agent tag", description="Agent tag used to filter searches.")
    agentVersion: int = Field(..., title="Last updated at", description="Last time the agent definition was updated in epoch milliseconds.", json_schema_extra={"format": "int64"})
    lastUpdatedByEmail: str = Field(..., title="Email", description="Email of the user who last updated the agent definition.")
    lastUpdatedByName: str = Field(..., title="Last updated by", description="Name of the user who last updated the agent definition.")
    isIndexed: bool = Field(False, title="Is Indexed", description="Whether the agent has been indexed in the search engine.")


class GetAllAgentsResponseModel(BaseResponseModel):
    agents: list[AgentItemModel] = Field(..., description="List of agents in the system.")
    nextCursor: str | None = Field(default=None, description="Opaque cursor to fetch the next page; pass it back as nextCursor. Null when there are no more results.")


class AgentResponseModel(BaseResponseModel):
    agentName: str = Field(..., description="Name of the agent")
    agentTitle: str = Field(..., description="Title of the agent.")
    agentTag: str = Field(..., title="Agent tag", description="Agent tag used to filter searches.")
    agentDefinition: AgentType = Field(..., description="Agent definition in JSON.")
    hasPastVersions: bool = Field(..., description="Whether this agent has past versions in the last three months.")
    lastUpdatedByName: str = Field(..., description="Name of the user who last updated the agent definition.")
    lastUpdatedByEmail: str = Field(..., description="Email of the user who last updated the agent definition.")
    agentVersion: int = Field(..., description="Agent version in epoch milliseconds.", json_schema_extra={"format": "int64"})
    isIndexed: bool = Field(False, title="Is Indexed", description="Whether the agent has been indexed in the search engine.")
    isLocked: bool = Field(False, title="Is Locked", description="Whether the agent is locked, which means an indexing job is running against it.")
    memoryLabels: list[str] = Field(default_factory=list, title="Memory labels",
                                    description="The labels this agent stores memories under. Deleting the agent deletes every user's memories under these labels.")
    invokedBy: list[str] = Field(default_factory=list, title="Invoked by",
                                 description="The published agents that invoke this agent. The agent cannot be deleted while this is not empty.")


class PastVersionModel(BaseModel):
    lastUpdatedByName: str = Field(..., description="Name of the user who updated this version.")
    lastUpdatedByEmail: str = Field(..., description="Email of the user who updated this version.")
    pastVersion: int = Field(..., description="Version in epoch milliseconds.", json_schema_extra={"format": "int64"})


class PastVersionsResponseModel(BaseResponseModel):
    pastVersions: list[PastVersionModel] = Field(..., description="List of past versions of a versioned object in the last three months.")


class GetDescriptorResponseModel(BaseResponseModel):
    descriptor: DescriptorModel = Field(default_factory=DescriptorModel, description="Descriptor definition in JSON.")
    lastDescriptorUpdatedByEmail: str | None = Field(default=None, description="Email of the user who last updated the agent descriptor.", title="Last updated by")
    lastDescriptorUpdatedByName: str | None = Field(default=None, description="Name of the user who last updated the agent descriptor.", title="Last updated by email")
    lastAgentUpdatedByName: str = Field(..., description="Name of the user who last updated the agent definition.")
    lastAgentUpdatedByEmail: str = Field(..., description="Email of the user who last updated the agent definition.")
    descriptorVersion: int = Field(default=0, description="Version of the descriptor, typically the epoch milliseconds time it was last updated.", json_schema_extra={"format": "int64"})
    agentVersion: int = Field(default=0, description="Version of the agent definition in epoch milliseconds.")
    agentTitle: str = Field(..., description="Title of the agent.")
    isLocked: bool = Field(default=False, description="Specifies whether the descriptor is locked, which means that it is being indexed at this time.")


class JobSubmittedResponseModel(BaseResponseModel):
    jobid: str = Field(default="", description="Identifier of the background job created for this request. Poll getIndexStatus with it to track progress.")


# ----- drafts -----

class CreateNewDraftResponseModel(BaseResponseModel):
    draftid: str = Field(default="", description="Identifier of the draft just created. Pass it to every other draft call.")
    draft: DraftItemModel


@dev_router.post("/createNewDraft", response_model=CreateNewDraftResponseModel, summary="Create a draft for a new agent", description="Creates a draft for a new agent with a placeholder definition and returns its draftid. The agent's name is chosen later through saveDraftNew.")
async def createNewDraft(item: EmptyRequestModel, request: Request) -> CreateNewDraftResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return CreateNewDraftResponseModel.model_validate(ret)


class CreateDraftFromAgentResponseModel(BaseResponseModel):
    draftid: str = Field(default="", description="Identifier of the draft, which for a draft of an existing agent is the agent name.")


@dev_router.post("/createDraftFromAgent", response_model=CreateDraftFromAgentResponseModel, summary="Create a draft for an existing agent", description="Creates a draft to make changes to an existing agent, and returns its draftid (the agent name). Succeeds whether the draft was created or already existed.")
async def createDraftFromAgent(item: AgentNameModel, request: Request) -> CreateDraftFromAgentResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return CreateDraftFromAgentResponseModel.model_validate(ret)


class SaveDraftNewModel(RequestModel):
    draftid: str = Field(..., description="Draft to update.")
    draftName: AgentName | None = Field(default=None, description="Name the agent will take when published. Omit to leave unchanged.")
    agentTitle: AgentTitle | None = Field(default=None, description="Omit to leave unchanged.")
    agentTag: AgentTag | None = Field(default=None, description="Omit to leave unchanged.")
    agentDefinition: _AgentDefinition | None = Field(default=None, description="Omit to leave unchanged.")
    validationQuery: str | None = Field(default=None, max_length=2000, description="Omit to leave unchanged.")


@dev_router.post("/saveDraftNew", response_model=BaseResponseModel, summary="Update a draft for a new agent",
                 description="Updates a draft that is not yet a published agent, where the name and tag are still the developer's to choose. Only draftid is required: any field left out keeps its current value.")
async def saveDraftNew(item: SaveDraftNewModel, request: Request) -> BaseResponseModel:
    _check_definition_length(item.agentDefinition)
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class SaveDraftAgentModel(RequestModel):
    draftid: str = Field(..., description="Draft to update. For a draft of an existing agent this is the agent name.")
    agentTitle: AgentTitle | None = Field(default=None, description="Omit to leave unchanged.")
    agentDefinition: _AgentDefinition | None = Field(default=None, description="Omit to leave unchanged.")
    validationQuery: str | None = Field(default=None, max_length=2000, description="Omit to leave unchanged.")


@dev_router.post("/saveDraftAgent", response_model=BaseResponseModel, summary="Update a draft of an existing agent",
                 description="Updates a draft taken from a published agent. The name and tag belong to the agent and cannot be changed here. Only draftid is required: any field left out keeps its current value.")
async def saveDraftAgent(item: SaveDraftAgentModel, request: Request) -> BaseResponseModel:
    _check_definition_length(item.agentDefinition)
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class SaveMergedDraftModel(RequestModel):
    draftid: str = Field(..., description="Draft to update.")
    agentDefinition: _AgentDefinition = Field(..., description="The merged agent definition.")
    agentVersion: int = Field(..., description="Version the merge was based on. The save is rejected if the draft has moved on since.")


@dev_router.post("/saveMergedDraft", response_model=BaseResponseModel, summary="Update a draft agent", description="Update an existing draft agent.")
async def saveMergedDraft(item: SaveMergedDraftModel, request: Request) -> BaseResponseModel:
    _check_definition_length(item.agentDefinition)
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class DraftHelpModel(RequestModel):
    userPrompt: str = Field(..., min_length=8, max_length=10000, description="What the developer wants the agent to do.")


class DraftHelpResponseModel(BaseResponseModel):
    agentDefinition: AgentType = Field(default="", description="An agent outline for the developer to finish. Nothing is saved: keep it by sending it to saveDraftNew or saveDraftAgent.")


@dev_router.post("/draftHelp", response_model=DraftHelpResponseModel, summary="Write an agent outline",
                 description="Writes an agent outline from a description of what it should do. The outline is returned, not saved, and a developer completes it: anything specific to your own systems, such as SQL or an API path, is left for you to fill in.")
async def draftHelp(item: DraftHelpModel, request: Request) -> DraftHelpResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return DraftHelpResponseModel.model_validate(ret)


@dev_router.post("/getDraft", response_model=DraftResponseModel, summary="Get a draft agent", description="Get a draft agent.")
async def getDraft(item: DraftidModel, request: Request) -> DraftResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return DraftResponseModel.model_validate(ret)


class PublishDraftResponseModel(BaseResponseModel):
    isIndexed: bool = Field(default=False, description="Whether the published agent is currently in the search index.")


@dev_router.post("/publishDraft", response_model=PublishDraftResponseModel, summary="Publish a draft agent", description="This publishes the draft agent to the system.")
async def publishDraft(item: DraftidModel, request: Request) -> PublishDraftResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return PublishDraftResponseModel.model_validate(ret)


class DeleteDraftModel(RequestModel):
    draftids: list[str] = Field(..., min_length=1, max_length=25, description="Drafts to delete, up to 25 at a time.")


@dev_router.post("/deleteDraft", response_model=BaseResponseModel, summary="Delete drafts", description="Deletes one or more draft agents. This has no effect on the system, as drafts exist purely in a developer's personal space.")
async def deleteDraft(item: DeleteDraftModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class GetDraftListModel(PagedRequestModel):
    limit: int = Field(default=10, ge=1, le=25, description="The maximum number of results to return.")


@dev_router.post("/getDraftList", response_model=GetAllDraftsResponseModel, summary="Get draft list",
                 description="Get all the drafts that have been created by this user.")
async def getDraftList(item: GetDraftListModel, request: Request) -> GetAllDraftsResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return GetAllDraftsResponseModel.model_validate(ret)


# ----- agents -----

class GetAgentListModel(PagedRequestModel):
    limit: int = Field(default=10, ge=1, le=1000, description="The maximum number of results to return.")


@dev_router.post("/getAgentList", response_model=GetAllAgentsResponseModel, summary="Get agent list",
                 description="Get all the agents in the system.")
async def getAgentList(item: GetAgentListModel, request: Request) -> GetAllAgentsResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return GetAllAgentsResponseModel.model_validate(ret)


@dev_router.post("/getAgent", response_model=AgentResponseModel, summary="Get an agent", description="Gets an agent definition.")
async def getAgent(item: AgentNameModel, request: Request) -> AgentResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentResponseModel.model_validate(ret)


class GetPastAgentVersionsModel(RequestModel):
    agentName: AgentName = Field(..., title="Agent name", description="The agent whose past versions are wanted.")


@dev_router.post("/getPastAgentVersions", response_model=PastVersionsResponseModel, summary="Gets past agent versions", description="Gets a list of past versions of an agent.")
async def getPastAgentVersions(item: GetPastAgentVersionsModel, request: Request) -> PastVersionsResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return PastVersionsResponseModel.model_validate(ret)


class GetPastAgentModel(RequestModel):
    agentName: AgentName = Field(..., title="Agent name", description="The agent the past version belongs to.")
    pastVersion: int


@dev_router.post("/getPastAgent", response_model=AgentResponseModel, summary="Get a past version of an agent", description="Gets a past version of an agent. Only the versions from the last three months are maintained.")
async def getPastAgent(item: GetPastAgentModel, request: Request) -> AgentResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return AgentResponseModel.model_validate(ret)


class UpdateTitleModel(RequestModel):
    agentName: AgentName = Field(..., description="Agent whose title is being changed.")
    agentTitle: AgentTitle = Field(..., min_length=1, description="New title for the agent.")


@dev_router.post("/updateTitle", response_model=BaseResponseModel, summary="Update an agent's title", description="Changes the title of one agent. The title is what users see when the agent is shown to them.")
async def updateTitle(item: UpdateTitleModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class UpdateTagModel(RequestModel):
    agentName: AgentName = Field(..., description="Agent whose tag is being changed.")
    agentTag: AgentTag = Field(..., description="New tag for the agent.")


@dev_router.post("/updateTag", response_model=BaseResponseModel, summary="Update an agent's tag", description="Changes the tag of one agent. The tag decides which searches can find the agent.")
async def updateTag(item: UpdateTagModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


@dev_router.post("/deleteAgent", response_model=BaseResponseModel, summary="Delete an agent", description="Deletes an agent from the system. This can be done only after removing the agent from the search index.")
async def deleteAgent(item: AgentNameModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


# ----- descriptors and indexing -----

@dev_router.post("/getDescriptor", response_model=GetDescriptorResponseModel, summary="Get an agent descriptor", description="Gets an agent descriptor. An agent descriptor describes the agent in a textual format. This is what a search matches a user query against.")
async def getDescriptor(item: AgentNameModel, request: Request) -> GetDescriptorResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    descriptor = ret.get("descriptor")
    if isinstance(descriptor, str) and descriptor:
        try:
            ret["descriptor"] = DescriptorModel.model_validate_json(
                await Encryptor.decrypt_query(request, descriptor))
        except Exception:
            ret["descriptor"] = DescriptorModel(description="Decryption error")
    elif isinstance(descriptor, str):
        ret["descriptor"] = DescriptorModel()
    return GetDescriptorResponseModel.model_validate(ret)


class PublishDescriptorModel(RequestModel):
    agentName: AgentName
    descriptor: DescriptorModel
    descriptorVersion: int = 0


class PublishDescriptorResponseModel(JobSubmittedResponseModel):
    validationError: str = Field(default="", description="Set when the descriptor was rejected by validation (for example, the description is too vague). No job is created in that case.")


@dev_router.post("/publishDescriptor", response_model=PublishDescriptorResponseModel, summary="Publish an agent descriptor",
                 description="Publish an agent descriptor. This submits a background job that indexes the agent descriptor in the search engine; poll getIndexStatus with the returned jobid to track it. Indexing can take several minutes.")
async def publishDescriptor(item: PublishDescriptorModel, request: Request) -> PublishDescriptorResponseModel:
    encrypted = await Encryptor.encrypt_query(request, item.descriptor.model_dump_json())
    ret = await RestCall.passthrough(request, {**item.model_dump(), "encrypted": encrypted})
    return PublishDescriptorResponseModel.model_validate(ret)


@dev_router.post("/deleteDescriptor", response_model=BaseResponseModel, summary="Delete a descriptor", description="Removes the agent from the search index so it can no longer be found by a search.")
async def deleteDescriptor(item: AgentNameModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class GetIndexStatusModel(RequestModel):
    jobid: str


class GetIndexStatusResponseModel(BaseResponseModel):
    jobid: str = ""
    status: Literal["submitted", "completed", "failed"] | None = Field(default=None, description="Current status of the job. Null when the job was not found (success is false).")
    message: str = Field(default="", description="Details on the job outcome, such as the error message when the job failed.")


@dev_router.post("/getIndexStatus", response_model=GetIndexStatusResponseModel, summary="Get the status of a previously submitted background job", description="publishDescriptor runs as a background job and returns a jobid. This call reports that job's status: submitted, completed or failed.")
async def getIndexStatus(item: GetIndexStatusModel, request: Request) -> GetIndexStatusResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return GetIndexStatusResponseModel.model_validate(ret)


# ----- notifications and docs -----

class NotificationModel(BaseModel):
    data: dict[str, JsonValue] = Field(..., description="What happened, as structured values rather than a sentence. Keys come from a fixed vocabulary: agent, part, name, action, old, new, fields, added, removed, reason. Only field names are reported for a configuration change, never the values. Render the text to show the user from the notification type and these values.")
    notificationType: NotificationType | None = Field(default=None, description="What the notification is about.")
    userEmail: str = Field(default="", description="Email of the user whose action raised the notification. Empty if that user no longer exists.")
    userName: str = Field(default="", description="Name of the user whose action raised the notification.")
    createdAt: int = Field(..., description="Time the notification was created, in epoch milliseconds.", json_schema_extra={"format": "int64"})


class GetNotificationsModel(ReportWindow):
    nextCursor: str | None = Field(default=None, description="Opaque cursor from a prior response's nextCursor. Omit or null to fetch the first page.")
    limit: int = Field(default=10, ge=1, le=25, description="The maximum number of results to return.")
    notificationType: NotificationType | None = Field(default=None, description="Only return notifications of this type. Cannot be combined with email.")
    userEmail: EmailStr | None = Field(default=None, description="Only return notifications raised by this user. Cannot be combined with notificationType.")

    @model_validator(mode="after")
    def _one_filter_only(self) -> Self:
        if self.userEmail is not None and self.notificationType is not None:
            raise ShowMessage("Filter by either email or notificationType, not both.")
        return self


class GetNotificationsResponseModel(BaseResponseModel):
    notifications: list[NotificationModel] = Field(default_factory=list)
    nextCursor: str | None = None


@dev_router.post("/getNotifications", response_model=GetNotificationsResponseModel, summary="Get notifications", description="Gets the workspace notifications, newest first — for example, submissions of agents for indexing or removal and their outcomes. Can be narrowed by time range and notification type.")
async def getNotifications(item: GetNotificationsModel, request: Request) -> GetNotificationsResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return GetNotificationsResponseModel.model_validate(ret)


class DocsQuestionRequestModel(RequestModel):
    question: SearchQuery


class DocsQuestionResponseModel(BaseResponseModel):
    answer: str


@dev_router.post("/docsQuestion", response_model=DocsQuestionResponseModel, summary="Answer to a docs question", description="Answer a question on Search2o documentation.")
async def docsQuestion(item: DocsQuestionRequestModel, request: Request) -> DocsQuestionResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return DocsQuestionResponseModel.model_validate(ret)


class SendHelpMessageRequestModel(RequestModel):
    subject: str = Field(default="Help", min_length=1, max_length=80, description="Subject of the help message.")
    message: str = Field(..., min_length=80, max_length=2000, description="The help message to send to Search2o support.")


class SendHelpMessageResponseModel(BaseResponseModel):
    email: str = Field(..., description="Email address support will reply to.")


@dev_router.post("/sendHelpMessage", response_model=SendHelpMessageResponseModel, summary="Send a help message", description="Sends a message to Search2o support. The reply goes to the email address of the user who sent it.")
async def sendHelpMessage(item: SendHelpMessageRequestModel, request: Request) -> SendHelpMessageResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return SendHelpMessageResponseModel.model_validate(ret)


class ApiConnectionPoolNamesResponseModel(BaseResponseModel):
    apiConnectionPoolNames: list[str] = Field(..., description="Names of the API connection pools defined in the system.")


@dev_router.post("/getApiConnectionPoolNames", response_model=ApiConnectionPoolNamesResponseModel, summary="Get the API connection pool names", description="Gets the names of the API connection pools defined in the system. LLM profiles, API profiles and agent server configs must use one of the pools named here.")
async def getApiConnectionPoolNames(item: EmptyRequestModel, request: Request) -> ApiConnectionPoolNamesResponseModel:
    await RestCall.call_method(request, "checkRole", {"role": UserRole.developer})
    return ApiConnectionPoolNamesResponseModel(success=True,
                                               apiConnectionPoolNames=await api_connection_pool_names(request))


class ValidateDraftModel(RequestModel):
    draftid: str
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    stream: bool = False
    convid: ConvId | None = None
    followup: bool = False


class DraftValidation(BaseModel):
    userEmail: str | None = Field(default=None)
    validationResults: ValidationResults = Field(default_factory=ValidationResults)
    configUpdatedAt: int = Field(default=0)
    draftAgentDefinition: AgentType | None = Field(default=None)
    convid: str


def _environment_problems(results: list[ValidationResult], runtime: RuntimeState) -> list[ValidationResult]:
    problems = []
    secrets = SecretsManager(runtime.secrets_model)
    for r in results:
        if r.vtype == ValidationResultType.allowlistItem and r.detail not in runtime.allowlist.eval_allowlist:
            problems.append(ValidationResult(vtype=r.vtype, path=r.path, detail=f"{r.detail!r} is not in the Allowlist."))
        elif r.vtype == ValidationResultType.secret:
            try:
                secrets.secret(r.detail)
            except ShowMessage:
                problems.append(ValidationResult(vtype=r.vtype, path=r.path, detail=f"Secret {r.detail!r} was not found."))
    return problems

async def _validate_draft_internal(item: ValidateDraftModel, request: Request, stream_iter: StreamIter | None,
                                run_ref: RunRef | None = None)-> ValidateDraftResponseModel:
    vr = ValidateDraftResponseModel(draftid=item.draftid, validationSuccess=False) # This enforces access
    stream_iter.trace(lambda: "Looking for compile errors and security checks on python expressions", TraceType.flow)
    try:
        validate_response = DraftValidation.model_validate(await RestCall.call_method(request, "validateDraft", {"draftid": item.draftid}))
        results = validate_response.validationResults.results
        vr.validationErrors = [r for r in results if r.vtype == ValidationResultType.error]
        if vr.validationErrors:
            runtime = Runtime.current()
        else:
            runtime = await Runtime.start_agent_exec(request, validate_response.configUpdatedAt, item.convid)
        vr.validationErrors += _environment_problems(results, runtime)
        if not vr.validationErrors:
            stream_iter.trace(lambda: "No compile errors and security concerns. Running the agent against the validation query", TraceType.flow)
            draft = DraftResponseModel.model_validate(await RestCall.passthrough_method(request, "getDraft", {"draftid": item.draftid})) # Same object includes both
            if draft.validationQuery:
                agent_exec = AgentExec.create_for_draft(draft.draftName, draft.agentTitle,
                                                        validate_response.draftAgentDefinition)
                if item.followup:
                    convid = validate_response.convid
                    state = await RestCall.get_state(request, convid)
                    if not state:
                        stream_iter.trace(lambda: "Could not find the state.", TraceType.error)
                        vr.runtimeError = "Validation cannot be run on the follow-up query as the stored state could not be found."
                        return vr
                else:
                    convid = validate_response.convid
                    state = None
                    item.inputs["query"] = draft.validationQuery

                sr = ExecStartResponseModel(convid=convid,
                                            userEmail=validate_response.userEmail,
                                            configUpdatedAt=validate_response.configUpdatedAt,
                                            isValidationRun=True)
                run = await ConversationRun.create(request, sr, item.inputs, agent_exec, stream_iter, state, run_ref)
                if run.paused_on_another_agent:
                    vr.runtimeError = (f"This draft's validation conversation is waiting for answers to the agent "
                                       f"{run.paused_on_another_agent!r}.")
                    return vr
                earm = await run.execute()
                vr.resultCode = earm.resultCode
                vr.convid = earm.convid
                vr.agentName = earm.agentName
                vr.askInput = earm.askInput
                if earm.resultCode == AgentExecResult.success.value:
                    stream_iter.trace(lambda: "Validation successful", TraceType.flow)
                    await RestCall.call_method(request, "setExecutionValidated", {"draftid": item.draftid})
                    vr.validationSuccess = True
                else:
                    stream_iter.trace(lambda: f"Agent responded with error message: {earm.error.message if earm.error else ''}", TraceType.error)
                    vr.runtimeError = earm.error.message if earm.error else None
            else:
                vr.runtimeError = "Must specify a query to validate a draft."
    except Exception as exc:
        detail = SensitiveString.safe_text(str(exc))
        name = type(exc).__name__
        vr.validationErrors.append(ValidationResult(vtype=ValidationResultType.error,
                                                    detail=f"Unexpected error: {name}: {detail}" if detail else f"Unexpected error: {name}"))
    finally:
        stream_iter.done_draft(vr)
    return vr


@dev_router.post("/validateDraftStream", summary="Validate a draft",
                  description="Runs the draft against its validation query, with tracing on. Progress and traces can be streamed with stream=true. A draft must validate before it can be published.",
                  response_model=ValidateDraftResponseModel,
                  responses={ 200: { "model": StreamDraftReturn } })
async def validateDraftStream(item: ValidateDraftModel, request: Request) -> StreamingResponse | ValidateDraftResponseModel:
    if item.stream:
        iter1 = StreamIter(should_trace=True)
        run_ref = RunRef()
        run = Runtime.track_task(asyncio.create_task(_validate_draft_internal(item, request, iter1, run_ref)))
        return StreamingResponse(
            stop_when_client_leaves(iter1, run, run_ref),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        iter1 = StreamIter(should_stream=False)
        return await _validate_draft_internal(item, request, iter1)
