# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://tactet.com/legal/license.html.

import os

from tactet.models.systemconfig import InitModel



class Config:
    whereUrl: str = os.environ.get("TACTET_WHERE_URL", "https://where.api.tactet.com").rstrip("/")
    cloudUrl: str = ""
    client_version: str = "0"
    license: str = ""
    node_name: str = ""
    init_model: InitModel | None = None




