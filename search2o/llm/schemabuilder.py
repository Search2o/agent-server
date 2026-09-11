# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from typing import Any

from pydantic import JsonValue

from search2o.common.exceptions import AGENT_PROBLEM, LlmError
from search2o.models.schemaobjects import FunctionArgModel


class SchemaBuilder:
    @classmethod
    def build(cls, task_name: str, args: dict[str, FunctionArgModel]) -> dict[str, JsonValue]:
        properties: dict[str, JsonValue] = {}
        required: list[str] = []

        for arg_name, spec in args.items():
            prop_schema = cls._arg_to_schema(task_name, spec)
            properties[arg_name] = prop_schema

            if spec.required:
                required.append(arg_name)

        root_schema: dict[str, JsonValue] = {
            "type": "object",
            "properties": properties,
            "additionalProperties": False
        }
        if required:
            root_schema["required"] = required
        return root_schema


    @classmethod
    def _arg_to_schema(cls, task_name: str, spec: FunctionArgModel) -> dict[str, JsonValue]:
        type_expr: str = spec.type.strip()

        # ---------------- Parsing helpers ----------------
        def split_top_level(s: str, sep: str) -> list[str]:
            out: list[str] = []
            depth = 0
            start = 0
            for i, ch in enumerate(s):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                elif ch == sep and depth == 0:
                    out.append(s[start:i].strip())
                    start = i + 1
            out.append(s[start:].strip())
            return [p for p in out if p != ""]

        def parse(expr: str):
            e = expr.strip()

            # Union with |
            union_parts = split_top_level(e, "|")
            if len(union_parts) > 1:
                return "union", [parse(p) for p in union_parts]

            # list[...]
            if e.lower().startswith("list[") and e.endswith("]"):
                inner = e[e.find("[") + 1 : -1]
                return "list", parse(inner)

            # dict[K, V]
            if e.lower().startswith("dict[") and e.endswith("]"):
                inner = e[e.find("[") + 1 : -1]
                parts = split_top_level(inner, ",")
                if len(parts) != 2:
                    raise LlmError(f"Syntax error in function {task_name}, parameter definition: dict[...] requires two arguments: {expr!r}",
                       AGENT_PROBLEM)
                k, v = parts
                return "dict", parse(k), parse(v)

            # Aliases and primitives
            aliases: dict[str, str] = {
                "string": "str",
                "number": "float",
                "boolean": "bool",
                "none": "null",
                "null": "null",
                "json": "any",
                "jsonvalue": "any",
                "object": "dict[str, any]",
                "mapping": "dict[str, any]",
            }
            low = e.lower()
            if low in {"str", "int", "float", "bool", "null", "any"}:
                return low
            if low in aliases:
                return parse(aliases[low])

            # Be permissive: unknown => any
            return "any"

        # ---------------- Schema synthesis ----------------
        def to_schema(node: Any) -> dict[str, JsonValue]:
            # primitives
            if isinstance(node, str):
                if node == "str":
                    return {"type": "string"}
                if node == "int":
                    return {"type": "integer"}
                if node == "float":
                    return {"type": "number"}
                if node == "bool":
                    return {"type": "boolean"}
                if node == "null":
                    return {"type": "null"}
                if node == "any":
                    return {}
                # fallback
                return {}

            kind = node[0]

            if kind == "list":
                items_schema = to_schema(node[1])
                return {"type": "array", "items": items_schema}

            if kind == "dict":
                key_node, val_node = node[1], node[2]
                value_schema = to_schema(val_node)

                # Keys must be strings in JSON; approximate other key types.
                if isinstance(key_node, str) and key_node in {"str", "any"}:
                    return {"type": "object", "additionalProperties": value_schema}
                if isinstance(key_node, str) and key_node == "int":
                    # integer-like keys as strings
                    return {
                        "type": "object",
                        "patternProperties": {"^-?\\d+$": value_schema},
                        "additionalProperties": False,
                    }
                # For unions or anything else, allow string key space.
                return {"type": "object", "additionalProperties": value_schema}

            if kind == "union":
                members = [to_schema(t) for t in node[1]]
                # If all members are simple {"type": "..."} we can compress to a type array.
                simple_types: list[str] = []
                others: list[dict[str, JsonValue]] = []
                for m in members:
                    t = m.get("type")
                    if isinstance(t, str) and set(m.keys()) == {"type"}:
                        simple_types.append(t)
                    else:
                        others.append(m)
                if others:
                    return {"anyOf": members}
                return {"type": simple_types}

            # Fallback
            return {}

        def schema_includes_type(s: dict[str, JsonValue], target: str) -> bool:
            t = s.get("type")
            if isinstance(t, str):
                return t == target
            if isinstance(t, list):
                return target in t
            if "anyOf" in s and isinstance(s["anyOf"], list):
                return any(
                    isinstance(x, dict) and schema_includes_type(x, target)
                    for x in s["anyOf"]  # type: ignore[call-arg]
                )
            return False

        parsed = parse(type_expr)
        schema: dict[str, JsonValue] = to_schema(parsed)

        # Layer in common annotations
        if spec.description:
            schema["description"] = spec.description

        return schema


    @classmethod
    def strip_gemini_dev_forbidden(cls, schema: dict[str, Any]) -> dict[str, Any]:
        FORBID = {"additionalProperties", "patternProperties", "oneOf", "anyOf", "allOf", "$ref"}
        ALLOWED = {"type", "description", "properties", "required", "items", "enum",
                   "format", "nullable", "title", "default", "maximum", "minimum", "pattern"}

        def walk(node: Any) -> Any:
            if isinstance(node, dict):
                # drop forbidden
                for k in list(node.keys()):
                    if k in FORBID:
                        node.pop(k, None)
                # recurse & prune unknowns (be conservative)
                for k in list(node.keys()):
                    v = node[k]
                    if k == "properties" and isinstance(v, dict):
                        node[k] = {str(p): walk(vp) for p, vp in v.items()}
                    elif k == "items":
                        node[k] = walk(v)
                    else:
                        node[k] = walk(v)
                    if k not in ALLOWED and k not in {"properties", "items"}:
                        node.pop(k, None)
                t = node.get("type")
                if isinstance(t, list):
                    non_null = [x for x in t if x != "null"]
                    if len(non_null) != len(t):
                        node["nullable"] = True
                    if non_null:
                        node["type"] = non_null[0]
                    else:
                        node.pop("type", None)
            elif isinstance(node, list):
                return [walk(x) for x in node]
            return node

        # work on a shallow copy
        return walk(schema)
