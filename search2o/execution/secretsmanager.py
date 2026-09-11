# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import os
import re

from search2o.common.exceptions import ShowMessage
from search2o.models.systemconfig import AgentSecretsModel, SecretSource, SecretConversionOptions


class SecretsManager:

    def __init__(self, model: AgentSecretsModel):
        self._model = model

    def __getitem__(self, name: str) -> str:
        return self.secret(name=name)

    def secret(self, name: str) -> str:
        if not name:
            raise ShowMessage("sys.secret called without a valid name")
        if name in self._model.cache:
            return self._model.cache[name]

        value = None
        if self._model.secretSource in (SecretSource.env, SecretSource.file):
            tname = name
            if self._model.transform:
                if self._model.transform.match:
                    tname = re.sub(self._model.transform.match, self._model.transform.replace, tname)
                if self._model.transform.convertTo != SecretConversionOptions.none:
                    match self._model.transform.convertTo:
                        case "lower":
                            tname = tname.lower()
                        case "upper":
                            tname = tname.upper()
            if self._model.secretSource == SecretSource.env:
                value = os.getenv(tname)
            elif self._model.secretSource == SecretSource.file:
                if os.path.isfile(tname):
                    with open(tname, 'r') as f:
                        value = f.read().strip()
            else:
                raise ShowMessage("Unexpected Secrets configuration. Please report this.")

        if value is not None:
            self._model.cache[name] = value
            return value
        else:
            raise ShowMessage(f"Secret {name!r} not found")
