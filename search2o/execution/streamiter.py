# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from search2o.common.enums import TraceType
from search2o.common.epoch import Epoch
from search2o.execution.runtime import Runtime
from search2o.models.apimodels import ExecAgentResponseModel, ValidateDraftResponseModel
from search2o.models.schemaobjects import ContentPartApi


class StreamProgressEnvelope(BaseModel):
    type: Literal["progress"] = "progress"
    value: str

class TraceObject(BaseModel):
    path: str = Field(default="", title="Path", description="Where in the agent this happened, such as "
                                                            "main.commands.if.then.output. Empty when the trace "
                                                            "does not belong to one command.")
    duration: int = Field(..., title="Duration", description="Milliseconds since the run started.",
                          json_schema_extra={"format": "int64"})
    message: str = Field(..., title="Message", description="What happened, written for the developer.")


class StreamTraceEnvelope(BaseModel):
    type: Literal["trace"] = "trace"
    traceType: TraceType = TraceType.flow
    value: TraceObject

class StreamDataEnvelope(BaseModel):
    type: Literal["data"] = "data"
    value: ContentPartApi

class StreamDraftEnvelope(BaseModel):
    type: Literal["draft"] = "draft"
    value: ValidateDraftResponseModel

class StreamAgentEnvelope(BaseModel):
    type: Literal["agent"] = "agent"
    value: ExecAgentResponseModel

class StreamNoopEnvelope(BaseModel):
    type: Literal["noop"] = "noop"

class StreamEndEnvelope(BaseModel):
    type: Literal["end"] = "end"

StreamDraftReturn = Annotated[Union[
    StreamProgressEnvelope, StreamTraceEnvelope, StreamDataEnvelope, StreamDraftEnvelope, StreamEndEnvelope
], Field(discriminator="type")]

StreamAgentReturn = Annotated[Union[
    StreamProgressEnvelope, StreamTraceEnvelope, StreamDataEnvelope,
    StreamAgentEnvelope, StreamNoopEnvelope, StreamEndEnvelope
], Field(discriminator="type")]

_StreamReturn = Union[
    StreamProgressEnvelope, StreamTraceEnvelope, StreamDataEnvelope,
    StreamDraftEnvelope, StreamAgentEnvelope, StreamNoopEnvelope, StreamEndEnvelope
]

class StreamIter(AsyncIterator[bytes]):
    def __init__(self, should_stream: bool = True, should_trace: bool = False) -> None:
        if should_stream:
            # Holds either bytes or the sentinel
            self._q: asyncio.Queue[_StreamReturn] = asyncio.Queue()
            self._done: bool = False
            self.start_time = Epoch.ms()
        self.is_real = should_stream
        self.should_trace = should_trace

    def progress(self, info: str) -> None:
        if self.is_real:
            self._q.put_nowait(StreamProgressEnvelope(value=info))

    def trace(self, msg_fn: Callable[[], object], trace_type: TraceType = TraceType.flow, path: str = "") -> None:
        if self.is_real and self.should_trace:
            msg = msg_fn()
            if msg:
                self._q.put_nowait(StreamTraceEnvelope(traceType=trace_type,
                                                       value=TraceObject(path=path, duration=self._duration_ms(),
                                                                         message=str(msg))))

    def data(self, obj: ContentPartApi) -> None:
        if self.is_real:
            self._q.put_nowait(StreamDataEnvelope(value=obj))

    def done_draft(self, response: ValidateDraftResponseModel) -> None:
        if self.is_real:
            self._q.put_nowait(StreamDraftEnvelope(value=response))
            self._q.put_nowait(StreamEndEnvelope())

    def done_agent(self, response: ExecAgentResponseModel) -> None:
        if self.is_real:
            response.output = None
            self._q.put_nowait(StreamAgentEnvelope(value=response))
            self._q.put_nowait(StreamEndEnvelope())

    # Async iterator protocol (what StreamingResponse consumes)
    def __aiter__(self) -> StreamIter:
        return self

    async def __anext__(self) -> bytes:
        if self.is_real:
            try:
                item = await asyncio.wait_for(self._q.get(), Runtime.current().validation.streamHeartbeat)
            except TimeoutError:
                return StreamNoopEnvelope().model_dump_json().encode("utf-8") + b"\n"
            if item.type == "end":
                raise StopAsyncIteration
            return item.model_dump_json().encode("utf-8") + b"\n"
        raise StopAsyncIteration

    def _duration_ms(self) -> int:
        return Epoch.ms() - self.start_time


