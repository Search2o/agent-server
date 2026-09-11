# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator


@asynccontextmanager
async def m_timeout(timeout: float | None) -> AsyncIterator[None]:
    if timeout is None:
        yield
    else:
        async with asyncio.timeout(timeout):
            yield

