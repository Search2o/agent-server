# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import base64
import hashlib

from fastapi import Request

from search2o.common.enums import CookieKey


class RequestHelper:
    @classmethod
    def token(cls, request: Request) -> str | None:
        auth = request.headers.get("Authorization")
        bearer = "bearer "
        if auth and auth[: len(bearer)].lower() == bearer:
            return auth[len(bearer):].strip()
        return request.cookies.get(CookieKey.cookieName, None)


    @classmethod
    def token_hash(cls, request: Request) -> str | None:
        token = cls.token(request)
        if token:
            digest = hashlib.sha256(f"v1:{token}".encode("utf-8")).digest()
            return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:10]
        return None
