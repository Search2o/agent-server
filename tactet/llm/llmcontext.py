# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://tactet.com/legal/license.html.

from __future__ import annotations

from tactet.common.mylogger import MyLogger
from tactet.llm.anthropicadapter import AnthropicAdapter
from tactet.llm.geminiadapter import GeminiAdapter
from tactet.llm.llmadapter import LlmAdapter
from tactet.llm.ollamaadapter import OllamaAdapter
from tactet.llm.openaiadapter import OpenaiAdapter
from tactet.llm.sglangadapter import SglangAdapter
from tactet.llm.vllmadapter import VllmAdapter
from tactet.models.systemconfig import LlmModel


class LlmContext:
    def __init__(self, llm: LlmModel, adapter: LlmAdapter):
        self.llm = llm
        self.adapter = adapter


class AllLlmContexts:
    def __init__(self, llms: dict[str, LlmModel], custom_adapters: list[LlmAdapter]):
        self.adapter_names: dict[str, str] = {}
        self.contexts: dict[str, LlmContext] = {}

        adapters: dict[str, LlmAdapter] = {}

        for obj in (AnthropicAdapter(), GeminiAdapter(), OpenaiAdapter(), OllamaAdapter(), VllmAdapter(), SglangAdapter()):
            adapters[obj.name()] = obj

        for obj in custom_adapters:
            adapters[obj.name()] = obj

        for name, llm in llms.items():
            adapter = adapters.get(llm.adapter)
            if adapter:
                self.contexts[name] = LlmContext(llm, adapter)
            else:
                MyLogger.error(f"Could not find adapter for LLM {name}")
                from tactet.common.rest_call import RestCall
                RestCall.report_error_once("An LLM profile names an adapter that does not exist.")

        self.adapter_names = {k: v.description() for k, v in adapters.items()}
