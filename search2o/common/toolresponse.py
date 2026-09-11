# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from dataclasses import dataclass

from pydantic import JsonValue


@dataclass
class ToolResponse:
    success: bool = False
    recoverable: bool = False
    response: dict[str, JsonValue] | None = None
    error_message: str = ""

