# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from enum import StrEnum, auto


class CaseSensitiveStrEnum(StrEnum):
    def _generate_next_value_(name, start, count, last_values):
        return name

    @classmethod
    def all(cls) -> set[str]:
        return {str(e.value) for e in cls}


# Keywords used in the agent's definition in JSON.
# noinspection PyEnum
class AgentWords(CaseSensitiveStrEnum):
    agent = auto()
    agentName = auto()
    agentVars = auto()
    agentVersion = auto()
    args = auto()
    assertv = "assert"
    body = auto()
    call = auto()
    callback = auto()
    command = auto()
    commands = auto()
    condition = auto()
    connection = auto()
    connectionString = auto()
    conversationVars = auto()
    customFields = auto()
    data = auto()
    default = auto()
    delete = auto()
    description = auto()
    do = auto()
    else_s = "else"
    end = auto()
    endThis = auto()
    error = auto()
    errorPrompt = auto()
    eventName = auto()
    followup = auto()
    forEach = auto()
    for_s = "for"
    function = auto()
    functions = auto()
    headers = auto()
    inc = auto()
    indexVar = auto()
    init = auto()
    inputs = auto()
    iter = auto()
    kwargs = auto()
    label = auto()
    level = auto()
    limit = auto()
    llmkey = auto()
    log = auto()
    logger = auto()
    loopVar = auto()
    main = auto()
    markdownFormat = auto()
    maxIndex = auto()
    maxIterations = auto()
    maxTokens = auto()
    maxToolCallLoops = auto()
    mcp = auto()
    message = auto()
    method = auto()
    name = auto()
    onError = auto()
    outputFormat = auto()
    parallelToolCall = auto()
    params = auto()
    postToolCall = auto()
    preToolCall = auto()
    profile = auto()
    prompt = auto()
    pydanticClass = auto()
    query = auto()
    result = auto()
    shareContext = auto()
    sharePrompts = auto()
    source = auto()
    sql = auto()
    start = auto()
    stateid = auto()
    stop = auto()
    store = auto()
    streamOutput = auto()
    structured = auto()
    structuredFormat = auto()
    system = auto()
    tag = auto()
    tags = auto()
    taskArgs = auto()
    taskName = auto()
    tasks = auto()
    temperature = auto()
    then = auto()
    timeout = auto()
    title = auto()
    toolCallMode = auto()
    toolChoice = auto()
    toolError = auto()
    tools = auto()
    topP = auto()
    type = auto()
    url = auto()
    user = auto()
    vendorTools = auto()
    version = auto()


class TraceType(CaseSensitiveStrEnum):
    flow = auto()   # Commands, functions and the agent itself starting; validation steps
    input = auto()  # What a command was called with: the LLM request, the API url, the SQL
    output = auto() # What a command returned: LLM content and tokens, the API response, row counts
    tool = auto()   # Tool calls made by the LLM: agent functions and MCP tools, with their results
    invoke = auto() # Nested agents
    agent = auto()  # The trace command written in the agent
    error = auto()  # Anything reporting a failure, including serialization warnings


class CookieKey(StrEnum):
    cookieName = "search2o_session"

