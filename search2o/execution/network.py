# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import re
from json import JSONDecodeError
from typing import Any
from collections.abc import Callable, Awaitable

import httpx
from httpx import Response, AsyncClient

from search2o.common.closable import Closable
from search2o.common.exceptions import ShowMessage
from search2o.common.sensitivestring import SensitiveString
from search2o.models.systemconfig import ApiConnectionPoolsModel

_RequestFn = Callable[..., Awaitable[Response]]

class Network(Closable):
    default_pool_name = "default"

    def __init__(self, model: ApiConnectionPoolsModel) -> None:
        super().__init__()
        self._model = model
        self.connection_pools: dict[str, AsyncClient] = {}

    def get_pool(self, name: str | None) -> AsyncClient:
        pname = name or self.default_pool_name
        pool = self.connection_pools.get(pname)
        if not pool:
            # Create pool
            pool_model = self._model.pools.get(pname)
            if not pool_model:
                raise ShowMessage(f"API connection pool '{pname}' not found")
            timeout = httpx.Timeout(
                connect=pool_model.timeout.connect,
                read=pool_model.timeout.read,
                write=pool_model.timeout.write,
                pool=pool_model.timeout.pool
            )
            pool = httpx.AsyncClient(follow_redirects=True,
                                               limits=httpx.Limits(
                                                   max_connections=pool_model.maxConnections,
                                                   max_keepalive_connections=pool_model.maxKeepaliveConnections,
                                                   keepalive_expiry=pool_model.keepaliveExpiry
                                               ), timeout=timeout)
            self.connection_pools[pname] = pool
        return pool

    async def close(self) -> None:
        for client in self.connection_pools.values():
            try:
                await client.aclose()
            except Exception:
                pass
        self.connection_pools.clear()


    async def _call(
            self,
            pname: str | None,
            fn: _RequestFn,
            url: str,
            **kwargs: Any,
    ) -> Response:
        try:
            ret = await fn(url, **kwargs)
            return ret
        except Exception as e:
            from search2o.common.mylogger import MyLogger
            MyLogger.error(f"Error ({type(e)}) connecting to URL in API connection pool {pname or self.default_pool_name}: {SensitiveString.safe_url(url)}")
            raise

    async def _get(self, pname: str | None, url: str, headers: dict[str, Any], params: dict[str, Any]) -> Response:
        if params is None:
            params = {}
        return await self._call(pname, self.get_pool(pname).get, url, headers=headers, params=params)

    async def _post(self, pname: str | None, url: str, headers: dict[str, Any], params: dict[str, Any], body: dict[str, Any]) -> Response:
        return await self._call(pname, self.get_pool(pname).post, url, headers=headers, params=params, json=body)


    async def _put(self, pname: str | None, url: str, headers: dict[str, Any], params: dict[str, Any], body: dict[str, Any]) -> Response:
        return await self._call(pname, self.get_pool(pname).put, url, headers=headers, params=params, json=body)


    async def _patch(self, pname: str | None, url: str, headers: dict[str, Any], params: dict[str, Any], body: dict[str, Any]) -> Response:
        return await self._call(pname, self.get_pool(pname).patch, url, headers=headers, params=params, json=body)


    async def _delete(self, pname: str | None, url: str, headers: dict[str, Any], params: dict[str, Any]) -> Response:
        return await self._call(pname, self.get_pool(pname).delete, url, headers=headers, params=params)

    text_patterns = ("xml", "html", "xhtml", "csv", "yaml")

    # Known binary content types
    binary_patterns = [
        r"^application/(octet-stream|pdf|zip|gzip|x-7z-compressed|x-rar-compressed|x-tar|x-bzip2)",
        r"^application/vnd\..*",  # e.g., vnd.ms-excel, vnd.openxmlformats-officedocument
        r"^application/x-.*",     # non-standard binary
        r"^image/",
        r"^audio/",
        r"^video/",
        r"^font/",
        r"^model/"
    ]


    def get_response(self, res: Response) -> Any | str | bytes | int:
        if not res.content:
            return res.status_code

        content_type = (
            res.headers.get("Content-Type", "")
            .partition(";")[0]
            .strip()
            .lower()
        )

        if content_type == "application/json" or content_type.endswith("+json"):
            try:
                return res.json()
            except JSONDecodeError:
                return res.text

        if content_type.startswith("text/") or any(
                pattern in content_type for pattern in self.text_patterns
        ):
            return res.text

        if any(
                re.search(pattern, content_type)
                for pattern in self.binary_patterns
        ):
            return res.content

        # Missing or unknown Content-Type.
        try:
            return res.json()
        except JSONDecodeError:
            return res.text


    async def call_rest(self, pname: str | None, api_type: str, url: str, headers: dict, params: dict, body: dict) -> Any:
        at = api_type.upper()
        if at == "GET":
            res: Response = await self._get(pname, url, headers=headers, params=params)
        elif at == "POST":
            res: Response = await self._post(pname, url, headers=headers, params=params, body=body)
        elif at == "PUT":
            res: Response = await self._put(pname, url, headers=headers, params=params, body=body)
        elif at == "PATCH":
            res: Response = await self._patch(pname, url, headers=headers, params=params, body=body)
        elif at == "DELETE":
            res: Response = await self._delete(pname, url, headers=headers, params=params)
        else:
            raise ShowMessage(f"Unknown API type {at}")
        return self.get_response(res)
