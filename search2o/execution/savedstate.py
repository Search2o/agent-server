# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

import json
import math
from typing import Any

from search2o.common.exceptions import ShowMessage
from search2o.execution.agent_state import ConversationState


def _dump(value: Any) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"))


def _saves_exactly(value: Any) -> bool:
    try:
        return _exact_text(value) is not None
    except (TypeError, ValueError, RecursionError):
        return False


def _exact_text(value: Any) -> str | None:
    text = _dump(value)
    text.encode("utf-8")
    return text if json.loads(text) == value else None


def _reason(value: Any) -> str:
    if isinstance(value, (set, frozenset)):
        return "is a set, which cannot be saved. Use a list instead."
    if isinstance(value, tuple):
        return "is a tuple, which would be saved as a list. Use a list instead."
    if isinstance(value, float) and not math.isfinite(value):
        return "is NaN or infinity, which cannot be saved."
    if isinstance(value, str):
        return "is text with an unpaired surrogate character, which cannot be saved."
    if hasattr(value, "__next__") or type(value).__name__ == "SerializationIterator":
        return "is a generator or iterator, which cannot be saved. Use a list instead."
    return f"is a value of type {type(value).__name__}, which cannot be saved."


def _locate(value: Any, path: list[Any], seen: set[int]) -> tuple[list[Any], str] | None:
    if _saves_exactly(value):
        return None
    if type(value) in (dict, list):
        if id(value) in seen:
            return path, "contains itself, which cannot be saved."
        seen = seen | {id(value)}
    if type(value) is dict:
        for k in value:
            if type(k) is not str:
                return path, f"has the key {k!r}, which is not text and would be saved as text. Use text keys."
        for k, v in value.items():
            found = _locate(v, path + [k], seen)
            if found:
                return found
    elif type(value) is list:
        for i, v in enumerate(value):
            found = _locate(v, path + [i], seen)
            if found:
                return found
    return path, _reason(value)


def _suffix(keys: list[Any]) -> str:
    return "".join(f"[{k}]" if isinstance(k, int) else f".{k}" for k in keys)


def _where(data: dict[str, Any], path: list[Any]) -> str:
    if len(path) >= 2 and path[0] == "conversationVars":
        return f"conv.{path[1]}{_suffix(path[2:])}"
    if len(path) >= 3 and path[0] == "agentVars":
        return f"agent.{path[2]}{_suffix(path[3:])} of agent {path[1]!r}"
    node: Any = data
    function = ""
    for i, key in enumerate(path):
        if isinstance(node, dict) and node.get("ntype") == "function":
            function = node.get("name", "")
            if key in ("localVars", "args") and i + 1 < len(path):
                kind = "Local variable" if key == "localVars" else "Argument"
                return f"{kind} '{path[i + 1]}{_suffix(path[i + 2:])}' of function {function!r}"
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            break
    where = _suffix(path).lstrip(".")
    return f"{where} in function {function!r}" if function else where


def saved_state_text(state: ConversationState) -> str:
    data = state.model_dump()
    try:
        text = _exact_text(data)
        if text is not None:
            return text
    except (TypeError, ValueError, RecursionError):
        pass
    found = _locate(data, [], set())
    where, reason = (_where(data, found[0]), found[1]) if found else ("The conversation state", "cannot be saved.")
    raise ShowMessage(f"The conversation could not be saved: {where} {reason}")
