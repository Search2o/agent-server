# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.
from __future__ import annotations

from enum import auto, StrEnum
from typing import Annotated, Any

from pydantic import Field, GetCoreSchemaHandler, GetJsonSchemaHandler, JsonValue, RootModel, ConfigDict
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema


SAFE_CODE_PATTERN = r"^[\x09\x0A\x0D\x20-\x7E]+$"  # allowed chars: \t \n \r and ASCII 0x20-0x7E
SAFE_EXPR_PATTERN = r"^(?:\{[\x20-\x7E\t\r\n]*\}|[^{][\s\S]*|\{(?:[\s\S]*[^}])?|)$"


class ExprString(str):
    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            source: type[Any],
            handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        str_schema = core_schema.str_schema(
            pattern=SAFE_EXPR_PATTERN,
            max_length=5000,
        )

        return core_schema.no_info_after_validator_function(
            cls,
            str_schema,
            ref="ExprString",
        )

    @classmethod
    def __get_pydantic_json_schema__(
            cls,
            schema: CoreSchema,
            handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema["title"] = "Static string like \" ... \" or a Python expression within braces, like \"{ ... }\""
        return json_schema


class SystemConfigPart(StrEnum):
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


class AuthMethod(StrEnum):
    builtin = auto()
    passwordless = auto()
    saml2 = auto()
    oidc = auto()


class AgentConfigPart(StrEnum):
    llm = auto()
    api = auto()
    mcp = auto()
    db = auto()
    prompt = auto()


identifierPattern = r"^[A-Za-z][A-Za-z0-9_]*[A-Za-z0-9]$"
identifierMinLength = 2

safeNamePattern = identifierPattern
safeNameMaxLength = 100

AgentName = Annotated[
    str,
    Field(
        min_length=identifierMinLength,
        max_length=32,
        pattern=identifierPattern,
    ),
]

SafeName = Annotated[str, Field(pattern=identifierPattern, max_length=safeNameMaxLength)]

ProfileName = Annotated[str, Field(pattern=identifierPattern, max_length=50)]

MemoryLabel = SafeName

serviceAccountNamePattern = r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?$"
ServiceAccountName = Annotated[str, Field(pattern=serviceAccountNamePattern, min_length=1, max_length=64)]


_tagBody = r"[a-z0-9]+(?:_[a-z0-9]+)*"

AgentTag = Annotated[str, Field(min_length=1, max_length=16, pattern=rf"^{_tagBody}$")]


SearchQuery = Annotated[str, Field(min_length=8, max_length=1000)]

TagFilter = Annotated[str, Field(max_length=16, pattern=rf"^(?:|{_tagBody})$")]


class DynamicDict(dict):
    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            source: type[Any],
            handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        dict_schema = core_schema.dict_schema(
            keys_schema=core_schema.str_schema(),
            values_schema=handler.generate_schema(JsonValue),
        )

        return core_schema.no_info_after_validator_function(
            cls,
            dict_schema,
            ref="DynamicDict",
        )

    @classmethod
    def __get_pydantic_json_schema__(
            cls,
            schema: CoreSchema,
            handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema["title"] = "A dictionary, where each string value can be a Python expression enclosed in braces, like \"{ ... }\""
        return json_schema


class PythonExpr(str):
    @classmethod
    def __get_pydantic_core_schema__(
            cls,
            source: type[Any],
            handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        str_schema = core_schema.str_schema(
            pattern=r"^\{[\x09\x0A\x0D\x20-\x7E]+\}$",
            max_length=2000,
        )

        return core_schema.no_info_after_validator_function(
            cls,
            str_schema,
            ref="PythonExpr",
        )

    @classmethod
    def __get_pydantic_json_schema__(
            cls,
            schema: CoreSchema,
            handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema["title"] = "Python expression within braces, like \"{ ... }\""
        return json_schema


class DynamicValue(RootModel[JsonValue]):
    model_config = ConfigDict(
        strict=True,
        allow_inf_nan=False,
        title="Dynamic JSON value",
        json_schema_extra={
            "description": "Any JSON-compatible scalar, array, or object.",
        },
    )
