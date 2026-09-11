# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import os

from search2o.models.systemconfig import InitModel



class Config:
    whereUrl: str = os.environ.get("SEARCH2O_WHERE_URL", "https://where.api.search2o.com").rstrip("/")
    cloudUrl: str = ""
    client_version: str = "0"
    license: str = ""
    node_name: str = ""
    init_model: InitModel | None = None




