# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit, urlunsplit


def split_query(url: str) -> tuple[str, dict[str, str]]:
    parts = urlsplit(url)
    if not parts.query:
        return url, {}
    return urlunsplit(parts._replace(query="")), dict(parse_qsl(parts.query, keep_blank_values=True))
