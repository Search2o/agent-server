# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

import os
import re
import time

from search2o.common.exceptions import ShowMessage
from search2o.execution.hooks import Hooks
from search2o.models.systemconfig import AgentSecretsModel, SecretSource, SecretConversionOptions

SecretCache = dict[str, tuple[str, float | None]]


class SecretsManager:

    def __init__(self, model: AgentSecretsModel, cache: SecretCache):
        self._model = model
        self._cache = cache
        self._fetched: dict[str, str] = {}

    def __getitem__(self, name: str) -> str:
        if not name:
            raise ShowMessage("sys.secret called without a valid name")
        if name in self._fetched:
            return self._fetched[name]
        cached = self._cached(name)
        if cached is not None:
            return cached
        if self._model.secretSource == SecretSource.vault:
            raise ShowMessage(f"Secret {name!r} was not fetched before the agent ran, and a vault secret cannot be "
                              f"read while it runs.")
        return self._keep(name, self._read_local(name))

    async def prefetch(self, names: list[str]) -> None:
        for name in names:
            if name in self._fetched:
                continue
            cached = self._cached(name)
            if cached is not None:
                self._fetched[name] = cached
                continue
            try:
                self._fetched[name] = self._keep(name, await self.fetch(name))
            except ShowMessage:
                pass

    async def fetch(self, name: str) -> str:
        if self._model.secretSource == SecretSource.vault:
            if not Hooks.has("vault"):
                raise ShowMessage("Secrets are set to come from a vault, but the vault hook is not set up.")
            value = await Hooks.call("vault", lambda: {"name": name})
            if value is None:
                raise ShowMessage(f"Secret {name!r} not found")
            return str(value)
        return self._read_local(name)

    def _cached(self, name: str) -> str | None:
        entry = self._cache.get(name)
        if entry is None:
            return None
        value, expires = entry
        if expires is not None and expires <= time.monotonic():
            self._cache.pop(name, None)
            return None
        return value

    def _keep(self, name: str, value: str) -> str:
        minutes = self._model.cacheMinutes
        if minutes != 0:
            self._cache[name] = (value, None if minutes < 0 else time.monotonic() + minutes * 60)
        return value

    def _transformed(self, name: str) -> str:
        transform = self._model.transform
        if transform:
            if transform.match:
                name = re.sub(transform.match, transform.replace, name)
            match transform.convertTo:
                case SecretConversionOptions.lower:
                    name = name.lower()
                case SecretConversionOptions.upper:
                    name = name.upper()
        return name

    def _read_local(self, name: str) -> str:
        value = None
        match self._model.secretSource:
            case SecretSource.env:
                value = os.getenv(self._transformed(name))
            case SecretSource.file:
                path = self._transformed(name)
                if os.path.isfile(path):
                    with open(path) as f:
                        value = f.read().strip()
            case _:
                raise ShowMessage("Unexpected Secrets configuration. Please report this.")
        if value is None:
            raise ShowMessage(f"Secret {name!r} not found")
        return value
