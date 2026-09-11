# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from pydantic import BaseModel, Field, JsonValue


class ATool(BaseModel):
    name: str = Field(..., title="Tool", description="The name of the tool")
    description: str | None = Field(default=None, title="Tool Description", description="The description of the tool. Optional in the MCP spec.")
    parameters: dict[str, JsonValue] = Field(..., title="Tool Parameters", description="The parameters of the tool")
