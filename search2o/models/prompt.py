# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, JsonValue

from search2o.models.schemaobjects import AgentFunctionModel


class AContentPart(BaseModel):
    additionalFields: dict[str, JsonValue] | None = Field(default=None, title="Additional fields", description="Vendor fields carried through unchanged, so they can be sent back on the next call.")


class TextPart(AContentPart):
    contentType: Literal["text"] = Field(default="text", title="Content type", description="Identifies this part as text.")
    text: str = Field(..., title="Text", description="The text of this part.")


class AContentMimePart(AContentPart):
    contentBase64: str = Field(..., title="Content", description="The part's bytes, base64 encoded.")
    mimeType: str = Field(default="", title="MIME type", description="The content's MIME type, such as image/png.")


class ImagePart(AContentMimePart):
    contentType: Literal["image"] = Field(default="image", title="Content type", description="Identifies this part as an image.")
    id_openai: str | None = Field(default=None, title="OpenAI image id", description="The id OpenAI gave this image, needed to reference it on a later call.")
    reasoning_openai: dict | None = Field(default=None, title="OpenAI reasoning item", description="The reasoning item OpenAI returned with the image, which must be sent back with it.")


type ContentPart = Annotated[TextPart | ImagePart, Field(discriminator="contentType")]


class ContentOutput(BaseModel):
    assistantResponseType: Literal["content"] = Field(default="content", title="Response type", description="Identifies this response as content rather than tool calls.")
    parts: list[ContentPart] = Field(default_factory=list, title="Parts", description="The parts the assistant produced.")


class ToolCall(BaseModel):
    id: str | None = Field(default=None, description="The id the vendor gave this tool call. Gemini does not supply one.", title="Call id")
    name: str = Field(..., title="Tool name", description="The tool the LLM asked to call.")
    args: dict[str, JsonValue] | str | None = Field(default=None, description="The arguments for the call. OpenAI sends these as a JSON string rather than an object.", title="Arguments")
    status: Literal["none", "in_progress", "completed"] = Field(default="none", description="How far the call has got. OpenAI only.", title="Status")
    additionalFields: dict[str, JsonValue] | None = Field(default=None, title="Additional fields", description="Vendor fields carried through unchanged, so they can be sent back on the next call.")


class ToolCalls(BaseModel):
    assistantResponseType: Literal["tool_call"] = Field(default="tool_call", title="Response type", description="Identifies this response as tool calls rather than content.")
    tools: list[ToolCall] = Field(default_factory=list, title="Tool calls", description="The calls the LLM asked for in this round.")


class AssistantResponse(BaseModel):
    promptElementType: Literal["assistant"] = Field(default="assistant", title="Element type", description="Identifies this prompt element as the assistant's turn.")
    response: Annotated[ToolCalls | ContentOutput, Field(discriminator="assistantResponseType")] = Field(..., title="Response", description="What the assistant returned: either content or tool calls.")


class UserEntry(BaseModel):
    promptElementType: Literal["user"] = Field(default="user", title="Element type", description="Identifies this prompt element as the user's turn.")
    entries: list[ContentPart] = Field(default_factory=list, title="Entries", description="The parts of the user's turn.")


class ToolResult(BaseModel):
    id: str = Field(..., title="Call id", description="The id of the tool call this answers.")
    name: str = Field(..., title="Tool name", description="The tool that was called.")
    result: dict[str, JsonValue] = Field(default_factory=dict, title="Result", description="What the tool returned. It must be JSON serializable to be sent to the LLM.")
    isError: bool = Field(default=False, description="Whether the tool call failed. The failure is recoverable: adapters flag it to the LLM so it can correct itself.", title="Is error")


class AMcpToolResult(BaseModel):
    contentType: Literal["text", "image", "audio", "URI", "resource"] = Field(default="text", title="Content type", description="What kind of content the MCP tool returned.")
    content: str = Field(..., title="Content", description="The content the MCP tool returned.")
    mimeType: str = Field(default="", title="MIME type", description="The content's MIME type, when it has one.")


class McpToolResult(BaseModel):
    content: list[AMcpToolResult] = Field(default_factory=list, title="Content", description="The parts the MCP tool returned.")


class ToolResults(BaseModel):
    promptElementType: Literal["tool_results"] = Field(default="tool_results", title="Element type", description="Identifies this prompt element as the results of a round of tool calls.")
    responses: list[ToolResult] = Field(default_factory=list, title="Results", description="One result per tool call in the round.")


type PromptElement = Annotated[UserEntry | AssistantResponse | ToolResults, Field(discriminator="promptElementType")]


class PromptModel(BaseModel):
    name: str = Field(default="default", title="Prompt name", description="The name this prompt is kept under in the conversation.")
    system: str = Field(default="", title="System prompt", description="The system prompt sent with every call on this prompt.")
    elements: list[PromptElement] = Field(default_factory=list, title="Elements", description="The conversation so far, in order.")


class McpToolModel(BaseModel):
    name: str = Field(..., title="Tool name", description="The tool's name, as the MCP server reports it.")
    description: str = Field(..., title="Description", description="What the tool does, as told to the LLM.")
    parameters: dict[str, JsonValue] = Field(..., title="Parameters", description="The tool's JSON Schema, as the MCP server reports it.")


class ToolChoiceModel(BaseModel):
    type: Literal["auto", "any", "none", "tool"] = Field(default="auto",
                                                         description="'auto', 'any' and 'none' mean what they mean to the vendors. 'tool' forces the tool named in toolName.", title="Tool choice")
    toolName: str | None = Field(default=None, description="Which tool to force. Set this only when the type is 'tool'.", title="Tool name")


class LlmRequestModel(BaseModel):
    vendor: str = Field(default="", description="The vendor named in the LLM profile.", title="Vendor")
    model: str = Field(default="", description="The model this call uses.", title="Model")

    url: str = Field(default="", title="Server URL", description="The LLM server URL, after the profile's expressions are evaluated.")
    headers: dict[str, JsonValue] = Field(default_factory=dict, title="HTTP headers", description="The request headers, after the profile's expressions are evaluated.")
    additionalParams: dict[str, JsonValue] = Field(default_factory=dict, title="Additional parameters", description="Extra parameters from the profile, merged over what the adapter produces.")

    retries: int = Field(
        default=0,
        description="How many times to retry. A request is retried only when the adapter sets should_retry - Gemini needs this, as some tool calls succeed on the second attempt.",
        ge=0, title="Retries")
    maxTokens: int = Field(default=5000, title="Max tokens", description="The token ceiling for this call.")

    prompt: PromptModel = Field(..., title="Prompt", description="The system prompt and the conversation to send.")
    mcpTools: list[McpToolModel] = Field(default_factory=list, title="MCP tools", description="The MCP tools offered to the LLM on this call.")
    agentFunctions: list[AgentFunctionModel] = Field(default_factory=list, title="Agent functions", description="The agent's own functions offered to the LLM as tools.")
    vendorTools: list[JsonValue] = Field(
        default_factory=list,
        description="Tools the LLM runs on its own side, such as web search.", title="Vendor tools")
    toolChoice: ToolChoiceModel | None = Field(default=None, title="Tool choice", description="Whether the LLM must call a tool, and which one. Unset leaves the choice to the vendor.")
    markdown: bool = Field(default=True, title="Markdown", description="Whether the answer is asked for as markdown.")


class LlmResponseModel(BaseModel):
    assistant: AssistantResponse | None = Field(default=None, title="Assistant response", description="What the LLM returned. Always set when the call succeeded.")
    inputTextTokens: int = Field(default=0, title="Input text tokens", description="Text tokens sent, used to price the call.")
    inputImageTokens: int = Field(default=0, title="Input image tokens", description="Image tokens sent, used to price the call.")
    outputTextTokens: int = Field(default=0, title="Output text tokens", description="Text tokens returned, used to price the call.")
    outputImageTokens: int = Field(default=0, title="Output image tokens", description="Image tokens returned, used to price the call.")

    should_retry: bool = Field(default=False, title="Should retry", description="Set by the adapter when the call is worth retrying.")
    did_succeed: bool = Field(default=False, title="Succeeded", description="Whether the call produced a usable response.")
    failure_reason: str = Field(default="", title="Failure reason", description="Why the call failed, for the message shown to the developer.")

    isMaxTokens: bool = Field(default=False, title="Hit token limit", description="Whether the answer was cut short by the token limit.")
    isFiltered: bool = Field(default=False, title="Filtered", description="Whether the vendor refused or filtered the answer.")
