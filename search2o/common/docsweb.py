# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import asyncio
from enum import StrEnum

import httpx
from pydantic import JsonValue

from search2o.common.exceptions import ShowMessage


class DocsWebType(StrEnum):
    agentschema = "agentschema"
    evaluationform = "evaluationform"
    uitext = "uitext"


class DocsWeb:
    _cache: dict[str, tuple[str, JsonValue]] = {}
    _locks: dict[str, asyncio.Lock] = {}
    _timeout = httpx.Timeout(10.0)

    @classmethod
    async def get(cls, dtype: DocsWebType) -> tuple[str, JsonValue]:
        from search2o.execution.runtime import Runtime
        url = f'{Runtime.docs_web.rstrip("/")}/{dtype}.json'
        lock = cls._locks.setdefault(dtype, asyncio.Lock())
        async with lock:
            cached = cls._cache.get(dtype)
            headers = {"If-None-Match": cached[0]} if cached and cached[0] else {}
            try:
                async with httpx.AsyncClient(timeout=cls._timeout) as client:
                    r = await client.get(url, headers=headers)
                if r.status_code == httpx.codes.NOT_MODIFIED and cached:
                    return cached
                r.raise_for_status()
                document = r.json()
            except Exception:
                if cached:
                    return cached
                raise ShowMessage(f"Could not read the {dtype} document.")
            result = (r.headers.get("ETag", ""), document)
            cls._cache[dtype] = result
            return result
