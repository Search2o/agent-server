# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from typing import Any


class FlowControlException(Exception):
    pass


class BreakException(FlowControlException):
    pass


class ContinueException(FlowControlException):
    pass


class ReturnFunctionException(FlowControlException):
    def __init__(self, val: Any):
        self.return_value = val

class AgentDone(FlowControlException):
    pass


class AgentStopped(FlowControlException):
    pass



class FailCommandException(FlowControlException):
    def __init__(self, message: Any, path: str = ""):
        self.message = message
        self.path = path

    def __str__(self) -> str:
        return str(self.message)
