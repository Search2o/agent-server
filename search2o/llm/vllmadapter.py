# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from search2o.llm.openaiadapter import OpenaiAdapter


class VllmAdapter(OpenaiAdapter):
    def name(self) -> str:
        return "vllm"

    def description(self) -> str:
        return "Adapter for vLLM's OpenAI compatible responses API"
