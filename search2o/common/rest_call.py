# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import traceback
from typing import Any, TYPE_CHECKING

import httpx
from fastapi import Request
from httpx import AsyncClient
from pydantic import BaseModel

from search2o.common.exceptions import ErrorFromCloudException, error_message
from search2o.common.mylogger import MyLogger
from search2o.common.requesthelper import RequestHelper
from search2o.config.config import Config
from search2o.models.systemconfig import ApiConnectionPoolModel

if TYPE_CHECKING:
    from search2o.execution.network import Network


class CloudErrorResponseModel(BaseModel):
    errorMessage: str
    errorData: dict[str, Any] | None = None

_REPORT_MESSAGE_MAX = 2000


class RestCall:
    ERROR_TIMEOUT = 5.0

    client: AsyncClient | None = None
    builtin_client: AsyncClient | None = None

    @classmethod
    async def init(cls):
        if cls.builtin_client:
            await cls.builtin_client.aclose()
        pool = ApiConnectionPoolModel()
        cls.builtin_client = httpx.AsyncClient(
            follow_redirects=True,
            limits=httpx.Limits(max_connections=pool.maxConnections,
                                max_keepalive_connections=pool.maxKeepaliveConnections,
                                keepalive_expiry=pool.keepaliveExpiry),
            timeout=httpx.Timeout(connect=pool.timeout.connect, read=pool.timeout.read,
                                  write=pool.timeout.write, pool=pool.timeout.pool))

    @classmethod
    async def close(cls):
        cls.client = None
        if cls.builtin_client:
            await cls.builtin_client.aclose()
            cls.builtin_client = None

    @classmethod
    async def get_builtin_client(cls) -> AsyncClient:
        if cls.builtin_client is None or cls.builtin_client.is_closed:
            await cls.init()
        return cls.builtin_client

    @classmethod
    def set_network(cls, network: Network) -> None:
        cls.client = network.get_pool(Config.init_model.agentServer.cloudPoolName)

    @classmethod
    async def get_client(cls) -> AsyncClient:
        if cls.client is None or cls.client.is_closed:
            return await cls.get_builtin_client()
        return cls.client

    @classmethod
    def url(cls, method: str) -> str:
        return f"{Config.cloudUrl}/{method.lstrip('/')}"

    @classmethod
    def get_method(cls, request: Request) -> str:
        path = request.url.path.rstrip("/")  # remove trailing slash
        return path.split("/")[-1]

    @classmethod
    async def passthrough(cls, request: Request, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await cls.call_method(request, cls.get_method(request), params)

    @classmethod
    async def passthrough_method(cls, request: Request, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return await cls.call_method(request, method, params)

    @classmethod
    async def call_method(cls, request: Request | None, method: str, params: dict[str, Any] | None = None, is_json: bool = True,
                          client: AsyncClient | None = None, timeout: float | None = None) -> dict[str, Any] | str:
        if params is None:
            params = {}
        headers = {
            "Accept": "application/json",
            "x-api-key": Config.license
        }
        if request:
            token = RequestHelper.token(request)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        params["clientVersion"] = Config.client_version
        params["nodeName"] = Config.node_name
        try:
            if client is None:
                client = await cls.get_client()
            if timeout is None:
                response = await client.post(cls.url(method), json=params, headers=headers)
            else:
                response = await client.post(cls.url(method), json=params, headers=headers, timeout=timeout)
            d = response.json() if is_json else response.text
        except Exception as e:
            raise ErrorFromCloudException(500, "Search2o cloud is currently down. Please try again in a few minutes.") from e

        if response.status_code != 200:
            if is_json:
                cer = CloudErrorResponseModel.model_validate(d)
                raise ErrorFromCloudException(response.status_code, cer.errorMessage, cer.errorData)
            else:
                return ""
        return d

    @classmethod
    async def save_state(cls, request: Request, name: str, content: str) -> dict[str, Any]:
        body_bytes = content.encode("utf-8")
        files: dict[str, tuple[str, bytes, str]] = { "file": (name, body_bytes, "text/plain; charset=utf-8") }
        headers = {
            "Accept": "application/json",
            "x-api-key": Config.license
        }
        if request:
            token = RequestHelper.token(request)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        try:
            client = await cls.get_client()
            response = await client.post(cls.url("saveState"), files=files, headers=headers)
            d = response.json()
        except Exception as e:
            raise ErrorFromCloudException(500, "Search2o is currently down. Please try again later.") from e
        if response.status_code != 200:
            cer = CloudErrorResponseModel(**d)
            raise ErrorFromCloudException(response.status_code, cer.errorMessage, cer.errorData)
        return d

    @classmethod
    async def get_state(cls, request: Request, convid: str) -> str:
        params = {}
        params["convid"] = convid
        return await cls.call_method(request, "getState", params, False)

    @classmethod
    async def report_error(cls, request: Request, message: str, exc: Exception)-> None:
        stacktrace = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        params = {}
        params["message"] = f"{message}: {error_message(exc)}"[:_REPORT_MESSAGE_MAX]
        params["stacktrace"] = stacktrace
        params["requestedMethod"] = cls.get_method(request)
        try:
            await cls.call_method(request, "reportError", params,
                                  client=await cls.get_builtin_client(), timeout=cls.ERROR_TIMEOUT)
        except Exception:
            MyLogger.error(f"Could not report error to the cloud: {message}")


