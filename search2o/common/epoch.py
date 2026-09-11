# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import time


class Epoch:
    @classmethod
    def ms(cls) -> int:
        return time.time_ns() // 1_000_000

