# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

class ExprHelper:
    @classmethod
    def get_expr(cls, val: str) -> str | None:
        if val.startswith("{") and val.endswith("}"):
            return val[1:-1].strip()
        else:
            return None

