# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio


class RunRef:
    def __init__(self) -> None:
        self.stop_requested = False
        self.stopped = asyncio.Event()

    def request_stop(self) -> None:
        self.stop_requested = True
        self.stopped.set()
