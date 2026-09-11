# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import asyncio

from fastapi import APIRouter, Request
from pydantic import Field, JsonValue
from starlette.responses import StreamingResponse

from search2o.execution.conversationrun import ConversationRun, ExecStartResponseModel
from search2o.common.rest_call import RestCall
from search2o.common.exceptions import ErrorFromCloudException
from search2o.models.schemaobjects import AgentExecResult, AgentTitleModel
from search2o.execution.runtime import Runtime
from search2o.execution.streamiter import StreamIter, StreamAgentReturn
from search2o.execution.runref import RunRef
from search2o.models.apimodels import BaseResponseModel, ErrorResponseModel, ExecAgentResponseModel, \
    RequestModel, SearchText, ConvId, cloud_search_query
from search2o.common.exceptions import error_message
from search2o.common.mylogger import MyLogger
from search2o.models.configtypes import AgentName, TagFilter
from search2o.models.systemconfig import SearchBehavior, FollowupBehavior

exec_router = APIRouter(prefix="/api/exec", tags=["exec"])


class ExecuteAgentModel(RequestModel):
    agentName: AgentName
    convid: ConvId | None = None
    inputs: dict[str, JsonValue] = Field(default_factory=dict)
    stream: bool = False

class SearchModel(RequestModel):
    query: SearchText = Field(..., description="The user's search query.")
    tag: TagFilter | None = Field(default=None, title="Filter tag",
                                  description="Filter searches by this tag. Set it to an empty string to search every tag.")

class SearchResponseModel(BaseResponseModel): # Sent straight to the UI
    searchResults: list[AgentTitleModel] = Field(default_factory=list,
                                                 description="The agents that matched the query, best match first.")
    searchBehavior: SearchBehavior
    followupBehavior: FollowupBehavior

@exec_router.post("/search", response_model=SearchResponseModel, summary="Search for agents",
                  description="Finds the agents that best match the search query.")
async def search(item: SearchModel, request: Request) -> SearchResponseModel:
    so = Runtime.current().search_options
    ret = await RestCall.passthrough_method(request, "search", {"query": cloud_search_query(item.query),
                                                                "tag": item.tag if item.tag is not None else so.tag})
    return SearchResponseModel(success=ret.get("success", True),
                               searchResults=ret.get("searchResults") or [],
                               searchBehavior=so.searchBehavior,
                               followupBehavior=so.followupBehavior)


async def stop_when_client_leaves(stream_iter: StreamIter, run: asyncio.Task, run_ref: RunRef):
    try:
        async for chunk in stream_iter:
            yield chunk
    finally:
        if not run.done():
            run_ref.request_stop()


@exec_router.post("/execAgent", summary="Execute an agent",
                  description="Execute an agent. Agent responses can be streamed with stream=true.",
                  response_model=ExecAgentResponseModel,
                  responses={ 200: { "model": StreamAgentReturn } })
async def execAgent(item: ExecuteAgentModel, request: Request) -> StreamingResponse | ExecAgentResponseModel:
    if item.stream:
        iter1 = StreamIter()
        run_ref = RunRef()
        run = Runtime.track_task(asyncio.create_task(_exec_agent_internal(item, request, iter1, run_ref)))
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
        return await _exec_agent_internal(item, request, iter1)


class UnknownConversation(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def _exec_agent_internal(item: ExecuteAgentModel, request: Request, iter1: StreamIter,
                            run_ref: RunRef | None = None) -> ExecAgentResponseModel:
    agent_name = item.agentName
    convid = item.convid
    try:
        if convid:
            state, start_agent_response = await asyncio.gather(
                RestCall.get_state(request, convid),
                        RestCall.passthrough_method(request, "startAgentExec",{ "isNewConv": False}))
            if not state:
                raise UnknownConversation("This conversation has expired. Please start a new one.")
        else:
            state = None
            start_agent_response = await RestCall.passthrough_method(request, "startAgentExec",
                                                                { "isNewConv": True})
        srm = ExecStartResponseModel.model_validate(start_agent_response)
        if not srm.convid:
            srm.convid = convid
        await Runtime.start_agent_exec(request, srm.configUpdatedAt, srm.convid)

        agent_exec = await Runtime.get_agent(request, agent_name)
        run = await ConversationRun.create(request, srm, item.inputs, agent_exec, iter1, state, run_ref)
        if run.paused_on_another_agent:
            raise UnknownConversation("This conversation is waiting for your answers to another agent. "
                                      "Continue it with that agent.")
    except ErrorFromCloudException as e:
        rc = AgentExecResult.mustLogin.name if e.status_code == 401 else AgentExecResult.callFailed
        ret = ExecAgentResponseModel(success=False, resultCode=rc, error=ErrorResponseModel(message=e.detail))
        iter1.done_agent(ret)
        return ret
    except UnknownConversation as e:
        ret = ExecAgentResponseModel(success=False, resultCode=AgentExecResult.unknownConversation, error=ErrorResponseModel(message=e.message))
        iter1.done_agent(ret)
        return ret
    except Exception as exc:
        MyLogger.error(f"Unexpected error executing the agent {agent_name!r} in conversation "
                       f"{convid or 'new'}: {type(exc).__name__}: {error_message(exc)}")
        ret = ExecAgentResponseModel(success=False, resultCode=AgentExecResult.unexpected, error=ErrorResponseModel(message="System issue in executing the agent. Please try later."))
        iter1.done_agent(ret)
        return ret

    ret = await run.execute()
    iter1.done_agent(ret)
    return ret

