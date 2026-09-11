# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from fastapi import APIRouter, Request
from pydantic import BaseModel, EmailStr, Field

from search2o.common.exceptions import ShowMessage
from search2o.common.mylogger import MyLogger
from search2o.common.rest_call import RestCall
from search2o.common.sensitivestring import SensitiveString
from search2o.execution.conversationrun import ConversationRun
from search2o.execution.agent_state import AgentOutput, ConversationState
from search2o.execution.encryptor import Encryptor
from search2o.execution.runtime import Runtime
from search2o.models.apimodels import BaseResponseModel, ConvId, EmptyRequestModel, PagedRequestModel, RequestModel
from search2o.models.schemaobjects import SearchHistoryModel, UiPrefModel, UserRole

user_router = APIRouter(prefix="/api/user", tags=["user"])


class UserProfileModel(BaseModel):
    email: EmailStr = Field(..., description="Email of the user.")
    userName: str = Field(..., description="Full name of this user or what the user prefers others to see them as")
    uiPref: UiPrefModel = Field(default_factory=UiPrefModel, description="UI preferences associated with this user")
    role: UserRole = Field(..., description="This user's role, which determines the actions that the user can execute in the system.")


class UserProfileResponseModel(BaseResponseModel):
    user: UserProfileModel = Field(..., description="The user who has access to this system.")


class PinnedConversationsResponseModel(BaseResponseModel):
    pinnedConversations: list[SearchHistoryModel] = Field(default_factory=list, description="Conversations this user has pinned. Pinned conversations are not returned in pages and do not expire.")


class UnpinnedConversationsResponseModel(BaseResponseModel):
    unpinnedConversations: list[SearchHistoryModel] = Field(default_factory=list, description="This user's recent conversations, most recently used first.")
    nextCursor: str | None = Field(default=None, description="Opaque cursor to fetch the next page; pass it back as nextCursor. Null when there are no more results.")


class ConversationElementModel(BaseModel):
    query: str = Field(..., description="The question the user asked.")
    response: AgentOutput = Field(..., description="The response from the agent")
    respondedAt: int = Field(..., description="The time the agent responded in epoch milliseconds.", json_schema_extra={"format": "int64"})


class GetConversationResponseModel(BaseResponseModel):
    convid: str | None = Field(default=None, description="ID of this conversation. This must be sent back for further questions to the same agent.")
    conversation: list[ConversationElementModel] = Field(default_factory=list, description="List of conversation elements")


class ConversationRequestModel(RequestModel):
    convid: ConvId


async def _decrypt_titles(request: Request, conversations: list) -> None:
    for c in conversations:
        if c.title:
            try:
                c.title = await Encryptor.decrypt_query(request, c.title)
            except Exception as e:
                c.title = "Decryption error"
                MyLogger.error(f"Could not decrypt the title of conversation {c.convid}: {SensitiveString.safe_text(str(e))}")


class ChangePasswordModel(RequestModel):
    currentPassword: str = Field(..., min_length=6, max_length=128, description="Current password of the user")
    newPassword: str = Field(..., min_length=6, max_length=128, description="New password of the user")


@user_router.post("/changePassword", response_model=BaseResponseModel, summary="Change user's password", description="This call is made when the user updates the password from the profile page in the UI.")
async def changePassword(item: ChangePasswordModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class UpdateUserProfileModel(RequestModel):
    userName: str = Field(..., min_length=2, max_length=100, description="Full name of this user or what the user prefers others to see them as")
    uiPref: UiPrefModel = Field(default_factory=UiPrefModel, description="UI preferences associated with this user")


@user_router.post("/updateUserProfile", response_model=BaseResponseModel, summary="Update user's profile and preferences", description="This call is made when the user updates their name or UI preferences.")
async def updateUserProfile(item: UpdateUserProfileModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


@user_router.post("/getUserProfile", response_model=UserProfileResponseModel, summary="Get the user profile", description="Gets the user profile. This is used to get the user's name and email address.")
async def getUserProfile(request: Request) -> UserProfileResponseModel:
    ret = await RestCall.passthrough(request, {})
    return UserProfileResponseModel.model_validate(ret)


@user_router.post("/getConversation", response_model=GetConversationResponseModel,
                  summary="Get a past conversation",
                  description="Gets the state of a previous conversation. This is called when the user clicks on past search results.",
                  )
async def getConversation(item: ConversationRequestModel, request: Request) -> GetConversationResponseModel:
    state = await RestCall.get_state(request, item.convid)
    if state:
        runtime = Runtime.current()
        state = await Encryptor.decrypt(request, runtime, state)
        agent_state = ConversationState.model_validate_json(state)
        conversation = []
        for run in agent_state.runs:
            conversation.append(ConversationElementModel(query=run.inputs.get("query", ''), response=run.output, respondedAt=run.execAt))
        return GetConversationResponseModel(conversation=conversation, success=True)
    else:
        raise ShowMessage("Could not get this conversation. It probably expired.", "This conversation has expired. Please start a new one.")


@user_router.post("/getPinnedConversations", response_model=PinnedConversationsResponseModel,
                  summary="Get pinned conversations",
                  description="Gets the conversations this user has pinned. Pinned conversations are returned in one call and do not expire.")
async def getPinnedConversations(item: EmptyRequestModel, request: Request) -> PinnedConversationsResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    rm = PinnedConversationsResponseModel.model_validate(ret)
    await _decrypt_titles(request, rm.pinnedConversations)
    return rm


class GetUnpinnedConversationsModel(PagedRequestModel):
    limit: int = Field(default=10, ge=1, le=25, description="The maximum number of results to return.")


@user_router.post("/getUnpinnedConversations", response_model=UnpinnedConversationsResponseModel,
                  summary="Get recent conversations",
                  description="Gets this user's recent unpinned conversations, most recently used first. These expire after ninety days.")
async def getUnpinnedConversations(item: GetUnpinnedConversationsModel, request: Request) -> UnpinnedConversationsResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    rm = UnpinnedConversationsResponseModel.model_validate(ret)
    await _decrypt_titles(request, rm.unpinnedConversations)
    return rm


class SetConversationTitleModel(RequestModel):
    convid: ConvId = Field(..., description="The conversation to rename.")
    title: str = Field(..., min_length=1, max_length=ConversationRun.ENCRYPTED_QUERY_MAX, description="New title for the conversation.")


@user_router.post("/setConversationTitle", response_model=BaseResponseModel,
                  summary="Rename a conversation",
                  description="Sets the title shown for a conversation in the user's list. By default a conversation is titled with its first query.")
async def setConversationTitle(item: SetConversationTitleModel, request: Request) -> BaseResponseModel:
    encrypted = await Encryptor.encrypt_query(request, item.title)
    ret = await RestCall.passthrough(request, {"convid": item.convid, "title": encrypted})
    return BaseResponseModel.model_validate(ret)


class SetPinnedModel(RequestModel):
    convid: ConvId = Field(..., description="The conversation to pin or unpin.")
    pinned: bool = Field(..., description="True to pin the conversation, false to unpin it.")


@user_router.post("/setPinned", response_model=BaseResponseModel,
                  summary="Pin or unpin a conversation",
                  description="Pins a conversation so it is kept and listed separately, or unpins it. There is a limit on how many conversations one user may pin.")
async def setPinned(item: SetPinnedModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, {"convid": item.convid, "pinned": item.pinned})
    return BaseResponseModel.model_validate(ret)


class DeleteConversationModel(RequestModel):
    convid: ConvId = Field(..., description="The conversation to delete.")


@user_router.post("/deleteConversation", response_model=BaseResponseModel,
                  summary="Delete a conversation",
                  description="Deletes one of the user's own conversations, along with everything the agent saved in it. This cannot be undone.")
async def deleteConversation(item: DeleteConversationModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class IntegrationTokenModel(BaseModel):
    tokenId: str = Field(..., title="Token id", description="Identifies this token, and is what revokeIntegrationToken takes.")
    name: str = Field(default="", title="Name", description="What the user called it when they created it, so they can tell one integration from another.")
    createdAt: int = Field(default=0, title="Created at", description="When the token was created, in epoch milliseconds.", json_schema_extra={"format": "int64"})
    lastUsedAt: int = Field(default=0, title="Last used at", description="When the token was last used, in epoch milliseconds. Zero when it never has been.", json_schema_extra={"format": "int64"})
    expiresAt: int | None = Field(default=None, title="Expires at", description="When the token stops working, in epoch milliseconds. Null when it does not expire.", json_schema_extra={"format": "int64"})


class CreateIntegrationTokenModel(RequestModel):
    name: str = Field(..., min_length=1, max_length=80, title="Name", description="What to call this token in the list, so it can be told apart from other integrations later.")


class CreateIntegrationTokenResponseModel(BaseResponseModel):
    tokenId: str = Field(default="", title="Token id", description="Identifies this token in the list and to revokeIntegrationToken.")
    token: str | None = Field(default=None, title="Token", description="The token to use as a Bearer credential. Returned once and never again, so it must be stored where it is going now.")
    tokenType: str = Field(default="", title="Token type", description="Type of token. Typically its value is 'Bearer'.")
    expiresIn: int = Field(default=0, title="Expires in", description="Seconds until the token expires, or 0 when it does not expire.")


class IntegrationTokensResponseModel(BaseResponseModel):
    tokens: list[IntegrationTokenModel] = Field(default_factory=list, title="Tokens", description="This user's integration tokens, newest first. The tokens themselves are never returned.")


class RevokeIntegrationTokenModel(RequestModel):
    tokenId: str = Field(..., min_length=1, max_length=64, title="Token id", description="The token to revoke.")


@user_router.post("/createIntegrationToken", response_model=CreateIntegrationTokenResponseModel,
                  summary="Create a token for an integration",
                  description="Creates a long-lived token that lets an integration act as this user, limited to what an end user may do. Because the user is already signed in, their password never reaches whatever holds the token. It is returned once.")
async def createIntegrationToken(item: CreateIntegrationTokenModel, request: Request) -> CreateIntegrationTokenResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return CreateIntegrationTokenResponseModel.model_validate(ret)


@user_router.post("/getIntegrationTokens", response_model=IntegrationTokensResponseModel,
                  summary="List this user's integration tokens",
                  description="What integrations can act as this user, when each was created and when it was last used, so that any of them can be revoked.")
async def getIntegrationTokens(item: EmptyRequestModel, request: Request) -> IntegrationTokensResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return IntegrationTokensResponseModel.model_validate(ret)


@user_router.post("/revokeIntegrationToken", response_model=BaseResponseModel,
                  summary="Revoke an integration token",
                  description="Stops that token working immediately. Nothing else is affected: not the user's browser session and not their other integrations.")
async def revokeIntegrationToken(item: RevokeIntegrationTokenModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)


class ApproveConnectModel(RequestModel):
    connectId: str = Field(..., min_length=1, max_length=64, title="Connect id", description="The connect request being approved or rejected.")
    approve: bool = Field(default=True, title="Approve", description="False rejects the request, so the integration stops waiting instead of timing out.")


@user_router.post("/approveConnect", response_model=BaseResponseModel,
                  summary="Approve an integration's connect request",
                  description="Approving mints a token for this user, limited to what an end user may do, and hands it to the integration that asked. The token is never returned to the browser.")
async def approveConnect(item: ApproveConnectModel, request: Request) -> BaseResponseModel:
    ret = await RestCall.passthrough(request, item.model_dump())
    return BaseResponseModel.model_validate(ret)

