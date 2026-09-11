# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from enum import auto, StrEnum
from typing import Annotated

from pydantic import Field


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


_tagBody = r"[a-z0-9]+(?:_[a-z0-9]+)*"

AgentTag = Annotated[str, Field(min_length=1, max_length=16, pattern=rf"^{_tagBody}$")]


SearchQuery = Annotated[str, Field(min_length=8, max_length=1000)]

TagFilter = Annotated[str, Field(max_length=16, pattern=rf"^(?:|{_tagBody})$")]
