# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from abc import ABC
from typing import Any


class InitializationError(Exception):
    ...

class ErrorFromCloudException(Exception):
    def __init__(self, status_code: int, em: str, error_data: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self.detail = em
        self.errorData = error_data

    def __str__(self) -> str:
        return self.detail


AGENT_PROBLEM = "This agent could not complete your request. The problem has been reported to its developer."
SERVICE_RETRY = "The agent could not reach a service it needs. Please try again in a moment."


class ErrorInAgent(Exception, ABC):
    USER_MESSAGE: str = AGENT_PROBLEM

    def __init__(self, m: str, user_m: str | None = None, path: str = "") -> None:
        self.m = m
        self.user_m = user_m
        self.path = path

    def message(self) -> str:
        return self.m

    def user_message(self) -> str:
        return self.user_m if self.user_m else self.USER_MESSAGE

    def __str__(self) -> str:
        return self.message()

class ShowMessage(ErrorInAgent):
    ...

class LlmError(ShowMessage):
    USER_MESSAGE = SERVICE_RETRY

    def message(self) -> str:
        return f"Error in LLM call: {super().message()}"

class InvokedAgentFailed(ErrorInAgent):
    def user_message(self) -> str:
        return self.user_m if self.user_m else self.m


def error_message(e: BaseException) -> str:
    return str(e) or type(e).__name__
