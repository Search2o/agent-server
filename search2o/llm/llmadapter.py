# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import JsonValue

from search2o.models.prompt import LlmRequestModel, LlmResponseModel


class LlmAdapter(ABC):
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    def process_request(self, req: LlmRequestModel) -> dict[str, JsonValue]:
        ...

    @abstractmethod
    def process_response(self, req: LlmRequestModel, response: dict[str, JsonValue]) -> LlmResponseModel:
        ...

    @abstractmethod
    def get_error(self, req: LlmRequestModel, response: dict[str, JsonValue]) -> str:
        ...


