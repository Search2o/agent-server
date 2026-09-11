# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from search2o.common.mylogger import MyLogger
from search2o.llm.anthropicadapter import AnthropicAdapter
from search2o.llm.geminiadapter import GeminiAdapter
from search2o.llm.llmadapter import LlmAdapter
from search2o.llm.openaiadapter import OpenaiAdapter
from search2o.models.systemconfig import LlmModel


class LlmContext:
    def __init__(self, llm: LlmModel, adapter: LlmAdapter):
        self.llm = llm
        self.adapter = adapter


class AllLlmContexts:
    def __init__(self, llms: dict[str, LlmModel], custom_adapters: list[LlmAdapter]):
        self.adapter_names: dict[str, str] = {}
        self.contexts: dict[str, LlmContext] = {}

        adapters: dict[str, LlmAdapter] = {}

        for obj in (AnthropicAdapter(), GeminiAdapter(), OpenaiAdapter()):
            adapters[obj.name()] = obj

        for obj in custom_adapters:
            adapters[obj.name()] = obj

        for name, llm in llms.items():
            adapter = adapters.get(llm.adapter)
            if adapter:
                self.contexts[name] = LlmContext(llm, adapter)
            else:
                MyLogger.error(f"Could not find adapter for LLM {name}")

        self.adapter_names = {k: v.description() for k, v in adapters.items()}
