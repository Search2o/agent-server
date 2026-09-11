# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import json

from pydantic import JsonValue

from search2o.common.enums import AgentWords


class ToolCallMethods:

    @classmethod
    def function_name(cls, name: str) -> str:
        return f"{AgentWords.function}_{name}"

    @classmethod
    def mcp_name(cls, name: str) -> str:
        return f"{AgentWords.mcp}_{name}"

    @classmethod
    def retrieve_name(cls, prefixed_name: str) -> tuple[str, str]:
        prefix, _, name = prefixed_name.partition("_")
        return prefix, name

    @classmethod
    def get_tool_args(cls, args: str | dict[str, JsonValue]) -> dict[str, JsonValue]:
        if isinstance(args, str):
            if args.strip():
                try:
                    return json.loads(args)
                except json.JSONDecodeError:
                    pass
            return {}
        else:
            return args

