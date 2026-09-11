# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import logging
import logging.config
import os
import socket
import uuid
from http import HTTPStatus
from pathlib import Path

import httpx

from search2o.common.exceptions import InitializationError, error_message
from search2o.config.config import Config
from search2o.models.systemconfig import InitModel
from importlib.metadata import PackageNotFoundError, version

_LICENSE_ENV = "SEARCH2O_LICENSE_KEY"
_LICENSE_FILE_ENV = "SEARCH2O_LICENSE_KEY_FILE"

_LICENSE_HELP_TEXT = """ \
    License key

A Search2o license key is required to run the server.
License keys are obtained from https://search2o.com.

Provide the key with ONE of these environment variables:

- SEARCH2O_LICENSE_KEY
The license key itself.
Example:
SEARCH2O_LICENSE_KEY=your-license-key

- SEARCH2O_LICENSE_KEY_FILE
The path to a file containing the license key.
Example:
SEARCH2O_LICENSE_KEY_FILE=/path/to/license.txt

Setting both is an error. If neither is set, or the key is empty, the server will exit.
"""


class BuildConfig:
    @classmethod
    def end(cls, message: str):
        print_message = f"{message}\n\n{_LICENSE_HELP_TEXT}"
        raise SystemExit(print_message)

    @classmethod
    def no_license_message(cls) -> str:
        message = f"One of {_LICENSE_ENV} or {_LICENSE_FILE_ENV} should be set, but neither is."
        typos = [n.replace("SEARCH2O", "SEARCH20") for n in (_LICENSE_ENV, _LICENSE_FILE_ENV)
                 if os.getenv(n.replace("SEARCH2O", "SEARCH20"), "").strip()]
        if typos:
            found = " and ".join(typos)
            has = "have" if len(typos) > 1 else "has"
            return (f"{message} But we found {found}, which {has} a zero instead of an o. "
                    f"This is probably a typo.")
        return message

    @classmethod
    def get_license(cls) -> tuple[str, str]:
        key = os.getenv(_LICENSE_ENV, "").strip()
        path_str = os.getenv(_LICENSE_FILE_ENV, "").strip()

        if key and path_str:
            raise InitializationError(
                f"{_LICENSE_ENV} and {_LICENSE_FILE_ENV} are both set. Set one of them, not both.")

        if path_str:
            path = Path(path_str)
            if not path.is_file():
                raise InitializationError(f"License file '{path}' not found")
            key = path.read_text(encoding="utf-8").strip()
            if not key:
                raise InitializationError(f"License file '{path}' is empty")

        if not key:
            raise InitializationError(cls.no_license_message())

        lic, _, suffix = key.partition("/")
        return lic, suffix

    @classmethod
    async def get_cloud_url(cls) -> str:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "x-api-key": Config.license,
        }
        payload: dict[str, str] = {
            "clientVersion": Config.client_version,
            "nodeName": Config.node_name,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(Config.whereUrl, headers=headers, json=payload, timeout=httpx.Timeout(20.0))
                if response.status_code == 200:
                    url = response.json().get("url")
                    if not url:
                        raise InitializationError("Search2o did not say where this account's API is. Please report.")
                    return url.rstrip("/")
                elif response.status_code == HTTPStatus.FORBIDDEN.value:
                    ret = response.json()
                    raise InitializationError(ret.get("errorMessage", "Invalid license key"))
                else:
                    raise InitializationError("Unexpected licensing error from Search2o. Please report.")
        except InitializationError:
            raise
        except Exception as e:
            raise InitializationError(f"Could not reach search2o.com to find this account's API: {error_message(e)}")

    @classmethod
    async def get_config(cls, config_name: str) -> InitModel | None:
        url = f"{Config.cloudUrl}/init"
        headers: dict[str, str] = {
            "Accept": "application/json",
            "x-api-key": Config.license,
        }
        payload: dict[str, str] = {
            "clientVersion": Config.client_version,
            "nodeName": Config.node_name,
            "configName": config_name
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=httpx.Timeout(20.0))
                if response.status_code == 200:
                    ret = response.json()
                    return InitModel.model_validate(ret.get("init"))
                elif response.status_code == HTTPStatus.FORBIDDEN.value:
                    ret = response.json()
                    raise InitializationError(ret.get("errorMessage", "Invalid license key"))
                else:
                    raise InitializationError("Unexpected licensing error from Search2o. Please report.")
        except InitializationError:
            raise
        except Exception as e:
            raise InitializationError(f"Could not download configuration from search2o.com: {error_message(e)}")


    @classmethod
    def get_node_name(cls) -> str:
        return f"{socket.gethostname()}-{str(uuid.uuid4())[:4]}"

    @classmethod
    async def fetch_and_build(cls) -> bool:
        try:
            Config.client_version = version("search2o")
        except PackageNotFoundError:
            Config.client_version = "0"
        Config.license, config_name = cls.get_license()
        Config.node_name = cls.get_node_name()
        Config.cloudUrl = await cls.get_cloud_url()
        Config.init_model = await cls.get_config(config_name)
        cls.set_loggers()
        return True

    @classmethod
    def set_loggers(cls):
        log_settings = Config.init_model.agentServer.logs
        if log_settings:
            logging.config.dictConfig(log_settings)

