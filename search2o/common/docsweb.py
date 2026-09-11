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
        from search2o.config.config import Config
        base = Config.init_model.docsweb.rstrip("/")
        async with httpx.AsyncClient(timeout=cls._timeout) as client:
            latest = await cls._fetch_latest(client, base, dtype)
            cached = cls._cache.get(dtype)
            if cached and cached[0] == latest:
                return cached
            lock = cls._locks.setdefault(dtype, asyncio.Lock())
            async with lock:
                cached = cls._cache.get(dtype)
                if cached and cached[0] == latest:
                    return cached
                document = await cls._fetch_doc(client, base, dtype, latest)
                cls._cache[dtype] = (latest, document)
                return latest, document

    @classmethod
    async def _fetch_latest(cls, client: httpx.AsyncClient, base: str, dtype: DocsWebType) -> str:
        try:
            r = await client.get(f"{base}/{dtype}_current.json")
            r.raise_for_status()
            latest = r.json().get("latest")
        except Exception:
            raise ShowMessage(f"Could not read the latest {dtype} version.")
        if not isinstance(latest, str) or not latest:
            raise ShowMessage(f"The latest {dtype} version is missing.")
        return latest

    @classmethod
    async def _fetch_doc(cls, client: httpx.AsyncClient, base: str, dtype: DocsWebType, latest: str) -> JsonValue:
        try:
            r = await client.get(f"{base}/{latest}/{dtype}.json")
            r.raise_for_status()
            return r.json()
        except Exception:
            raise ShowMessage(f"Could not read the {dtype} document.")
