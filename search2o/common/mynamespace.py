# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from types import SimpleNamespace
from typing import Annotated, Any, ClassVar

from pydantic import JsonValue, PlainSerializer, PlainValidator, TypeAdapter, ValidationError

from search2o.models.schemaobjects import ReadOnlyVariable


class MyNamespace(SimpleNamespace):
    _namespace_name: ClassVar[ReadOnlyVariable]

    def __init__(
            self,
            values: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(**(values or {}))

    def __getattr__(self, attribute: str) -> Any:
        ns = type(self).__dict__.get("_namespace_name")
        ns_name = ns.value if ns is not None else type(self).__name__
        raise AttributeError(
            f"{ns_name} has no attribute {attribute!r}",
            name=attribute,
            obj=self,
        )

class AgentNamespace(MyNamespace):
    _namespace_name = ReadOnlyVariable.agent

class ConvNamespace(MyNamespace):
    _namespace_name = ReadOnlyVariable.conv

class CommandNamespace(MyNamespace):
    _namespace_name = ReadOnlyVariable.command


_json_object_adapter = TypeAdapter(dict[str, JsonValue])
_json_value_adapter = TypeAdapter(JsonValue)


def _validate_agent_namespace(value: Any) -> AgentNamespace:
    if isinstance(value, AgentNamespace):
        return value

    values = _json_object_adapter.validate_python(value)
    return AgentNamespace(values)


def _validate_conv_namespace(value: Any) -> ConvNamespace:
    if isinstance(value, ConvNamespace):
        return value

    values = _json_object_adapter.validate_python(value)
    return ConvNamespace(values)


def _serialize_namespace(
        value: MyNamespace,
) -> dict[str, JsonValue]:
    out: dict[str, JsonValue] = {}
    for k, v in vars(value).items():
        try:
            out[k] = _json_value_adapter.validate_python(v)
        except ValidationError:
            pass
    return out


AgentNamespaceField = Annotated[
    AgentNamespace,
    PlainValidator(
        _validate_agent_namespace,
        json_schema_input_type=dict[str, JsonValue],
    ),
    PlainSerializer(
        _serialize_namespace,
        return_type=dict[str, JsonValue],
    ),
]


ConvNamespaceField = Annotated[
    ConvNamespace,
    PlainValidator(
        _validate_conv_namespace,
        json_schema_input_type=dict[str, JsonValue],
    ),
    PlainSerializer(
        _serialize_namespace,
        return_type=dict[str, JsonValue],
    ),
]

