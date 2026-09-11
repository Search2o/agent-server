# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

import math
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

# JsonValue as in pydantic
JsonValue = (
        str
        | int
        | float
        | bool
        | None
        | list["JsonValue"]
        | dict[str, "JsonValue"]
)


class SensitiveString:
    # --- patterns & constants ---

    # Key-name hints (for safe_string)
    _SENSITIVE_KEYWORDS = re.compile(
        r"""
        (?i)                # case-insensitive
        (
            pass(word)?     | pwd
          | secret
          | api[_-]?key
          | token
          | bearer
          | jwt
          | auth
          | session
          | cookie
          | private
          | ssh
          | cert
          | credit
          | card
          | ssn
        )
        """,
        re.VERBOSE,
    )

    # Value-shape hints
    _JWT_REGEX = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
    _BASE64ISH_REGEX = re.compile(r"^[A-Za-z0-9+/=]{20,}$")
    _HEX_LONG_REGEX = re.compile(r"^[0-9a-fA-F]{32,}$")
    _EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    _CREDIT_CARD_DIGITS = re.compile(r"\b\d{13,19}\b")

    _PRIVATE_KEY_MARKERS: tuple[str, ...] = (
        "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "-----BEGIN CERTIFICATE-----",
    )

    _SECRET_PREFIXES: tuple[str, ...] = (
        "sk-",          # OpenAI etc
        "rk_", "pk_live_", "pk_test_",
        "ghp_", "gho_",      # GitHub PATs
        "xoxb-", "xoxp-",    # Slack tokens
        "AKIA", "ASIA",      # AWS access keys
        "SG.",               # SendGrid
        "RGAPI-",            # Riot API
        "eyJ",               # very common JWT header prefix
    )

    # For URI query param names + connection-string keys
    _SENSITIVE_PARAM_SUBSTRINGS: tuple[str, ...] = (
        "pass",
        "pwd",
        "password",
        "secret",
        "token",
        "apikey",
        "api_key",
        "key",
        "auth",
        "signature",
        "sig",
        "sas",
        "cred",
        "credential",
    )


    @staticmethod
    def _to_str(value: Any) -> str:
        if isinstance(value, (bytes, bytearray)):
            return value.decode("utf-8", errors="ignore").strip()
        return str(value).strip()

    @staticmethod
    def _mask_value_str(s: str) -> str:
        if not s:
            return "***"
        if len(s) <= 2:
            return "***"
        return f"{s[0]}***{s[-1]}"

    @classmethod
    def _is_sensitive_param_name(cls, name: str) -> bool:
        lowered = name.lower()
        return any(fragment in lowered for fragment in cls._SENSITIVE_PARAM_SUBSTRINGS)

    @staticmethod
    def _shannon_entropy(s: str) -> float:
        if not s:
            return 0.0
        freq: dict[str, int] = {}
        for ch in s:
            freq[ch] = freq.get(ch, 0) + 1
        length = len(s)
        entropy = 0.0
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def _luhn_check(number: str) -> bool:
        total = 0
        reverse_digits = number[::-1]
        for idx, ch in enumerate(reverse_digits):
            d = ord(ch) - 48  # int(ch)
            if idx % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return total % 10 == 0

    @classmethod
    def _string_looks_sensitive(cls, key: str | None, s: str) -> bool:
        if not s:
            return False

        # Key name hints
        if key and cls._SENSITIVE_KEYWORDS.search(key):
            return True

        # Private key / cert blocks
        if any(marker in s for marker in cls._PRIVATE_KEY_MARKERS):
            return True

        # Known secret prefixes
        if any(s.startswith(pref) for pref in cls._SECRET_PREFIXES):
            return True

        # Tokens / hashes
        if cls._JWT_REGEX.match(s):
            return True
        if cls._BASE64ISH_REGEX.match(s):
            return True
        if cls._HEX_LONG_REGEX.match(s):
            return True

        # PII-ish things
        if cls._EMAIL_REGEX.search(s):
            return True

        for m in cls._CREDIT_CARD_DIGITS.finditer(s):
            digits = m.group(0)
            if cls._luhn_check(digits):
                return True

        if re.search(r"\b\d{3}-\d{2}-\d{4}\b", s):  # SSN-like
            return True

        # High-entropy long strings
        if len(s) >= 16:
            if s.startswith("http://"):
                s = s.removeprefix("http://")
            elif s.startswith("https://"):
                s = s.removeprefix("https://")
            ent = cls._shannon_entropy(s)
            if ent >= 3.5:
                return True

        return False


    @classmethod
    def safe_connection_string(cls, connection_string: str) -> str:
        s = cls._to_str(connection_string)
        if not s:
            return s

        if re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*://", s):
            # Mask the password in "scheme://user:PASSWORD@" (username kept, like ODBC keeps User Id).
            masked = re.sub(
                r"(://[^:/?#@\s]+):([^@\s]*)@",
                lambda m: f"{m.group(1)}:{cls._mask_value_str(m.group(2))}@",
                s,
                count=1,
            )
            # Also mask sensitive query-param values: "...?password=xyz&sslkey=abc".
            if "?" in masked:
                head, _, query = masked.partition("?")
                masked_q: list[str] = []
                for part in query.split("&"):
                    if "=" in part:
                        name, value = part.split("=", 1)
                        if cls._is_sensitive_param_name(name):
                            masked_q.append(f"{name}={cls._mask_value_str(value)}")
                            continue
                    masked_q.append(part)
                masked = f"{head}?{'&'.join(masked_q)}"
            return masked

        parts: list[str] = []
        buf: list[str] = []
        quote: str | None = None
        for ch in s:
            if quote:
                buf.append(ch)
                if ch == quote:
                    quote = None
            elif ch in ("'", '"'):
                quote = ch
                buf.append(ch)
            elif ch == ";":
                parts.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        parts.append("".join(buf))

        masked_parts: list[str] = []

        for part in parts:
            raw = part
            stripped = raw.strip()
            if not stripped or "=" not in stripped:
                # Empty / not key=value / comments – keep as-is
                masked_parts.append(raw)
                continue

            # Preserve leading spaces
            leading_len = len(raw) - len(raw.lstrip(" "))
            leading = raw[:leading_len]
            rest = raw[leading_len:]

            key, value = rest.split("=", 1)
            key_stripped = key.strip()

            if not cls._is_sensitive_param_name(key_stripped):
                masked_parts.append(raw)
                continue

            # Handle quotes around value ("abc", 'abc')
            value_stripped = value.strip()
            if value_stripped and value_stripped[0] in ("'", '"') and value_stripped[-1] == value_stripped[0]:
                quote = value_stripped[0]
                inner = value_stripped[1:-1]
                masked_inner = cls._mask_value_str(inner)
                new_value = f"{quote}{masked_inner}{quote}"
            else:
                new_value = cls._mask_value_str(value_stripped) if value_stripped else "***"

            masked_parts.append(f"{leading}{key}={new_value}")

        return ";".join(masked_parts)


    @classmethod
    def safe_url(cls, url: str) -> str:
        s = cls._to_str(url)
        if not s:
            return s

        parsed = urlparse(s)
        if parsed.scheme not in ("http", "https"):
            # Not a URL we recognize → return unchanged
            return s

        # Mask userinfo: user:pass@
        username = parsed.username
        password = parsed.password
        hostname = parsed.hostname
        port = parsed.port

        netloc = ""
        if username is not None or password is not None:
            user_part = cls._mask_value_str(username) if username is not None else "***"
            netloc += user_part
            if password is not None:
                netloc += ":" + cls._mask_value_str(password)
            netloc += "@"

        if hostname:
            netloc += hostname
        if port is not None:
            netloc += f":{port}"

        if not netloc:
            netloc = parsed.netloc

            # Mask sensitive query parameters while preserving original encoding.
        if parsed.query:
            query_parts = parsed.query.split("&")
            masked_query_parts: list[str] = []

            for part in query_parts:
                if "=" not in part:
                    masked_query_parts.append(part)
                    continue

                name, value = part.split("=", 1)

                if cls._is_sensitive_param_name(name):
                    masked_query_parts.append(f"{name}={cls._mask_value_str(value)}")
                else:
                    masked_query_parts.append(part)

            masked_query = "&".join(masked_query_parts)
        else:
            masked_query = parsed.query

        masked = parsed._replace(netloc=netloc, query=masked_query)
        return urlunparse(masked)


    @classmethod
    def safe_dict(cls, data: dict[str, JsonValue] | None) -> dict[str, JsonValue]:

        def _scrub(value: JsonValue, key: str | None) -> JsonValue:
            # dict -> build a new dict
            if isinstance(value, dict):
                return {k: _scrub(v, k) for k, v in value.items()}

            # list -> build a new list
            if isinstance(value, list):
                return [_scrub(item, key) for item in value]

            # primitive
            s = cls._to_str(value)
            if cls._string_looks_sensitive(key, s):
                return cls._mask_value_str(s)

            return value

        if not data:
            return {}

        # Top-level is dict[str, JsonValue]; keep type consistent
        return _scrub(data, None)  # type: ignore[return-value]


    @classmethod
    def safe_text(cls, text: Any) -> str:
        s = cls._to_str(text)
        if not s:
            return s

        # Private key / cert blocks: do not try to preserve content.
        if any(marker in s for marker in cls._PRIVATE_KEY_MARKERS):
            return "[redacted private key or certificate block]"

        # Mask URLs embedded in the error text.
        def _mask_url_match(match: re.Match[str]) -> str:
            return cls.safe_url(match.group(0))

        s = re.sub(r"https?://[^\s\"'<>]+", _mask_url_match, s)

        sensitive_name = (
            r"(?:"
            r"authorization|proxy-authorization|x-api-key|api[_-]?key|apikey|"
            r"access[_-]?token|refresh[_-]?token|id[_-]?token|token|secret|"
            r"client[_-]?secret|password|passwd|pwd|bearer|session|cookie|"
            r"signature|sig|credential|credentials|auth"
            r")"
        )

        pattern = re.compile(
            rf"""
            (?ix)
            (?P<prefix>
                ["']?{sensitive_name}["']?
                \s*
                (?:
                    :|=|
                    =>
                )
                \s*
                (?:
                    bearer\s+
                )?
                ["']?
            )
            (?P<value>
                [^"',;\s\}}\]\)]+
            )
            (?P<suffix>["']?)
            """,
            re.VERBOSE,
        )

        def _mask_kv_match(match: re.Match[str]) -> str:
            value = match.group("value")
            return f"{match.group('prefix')}{cls._mask_value_str(value)}{match.group('suffix')}"

        s = pattern.sub(_mask_kv_match, s)

        s = re.sub(
            r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{8,})",
            lambda m: "Bearer " + cls._mask_value_str(m.group(1)),
            s,
        )

        # Known secret-looking standalone tokens.
        token_pattern = re.compile(
            r"""
            (?x)
            \b(
                sk-[A-Za-z0-9_-]{8,} |
                rk_[A-Za-z0-9_-]{8,} |
                pk_(?:live|test)_[A-Za-z0-9_-]{8,} |
                gh[po]_[A-Za-z0-9_]{8,} |
                xox[bp]-[A-Za-z0-9-]{8,} |
                AKIA[0-9A-Z]{12,} |
                ASIA[0-9A-Z]{12,} |
                SG\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,} |
                RGAPI-[A-Za-z0-9-]{8,} |
                eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+
            )\b
            """,
            re.VERBOSE,
        )

        s = token_pattern.sub(lambda m: cls._mask_value_str(m.group(1)), s)

        # Long JWTs that do not start with eyJ.
        s = re.sub(
            r"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
            lambda m: cls._mask_value_str(m.group(0)),
            s,
        )

        # Credit cards / SSN-like values.
        s = cls._CREDIT_CARD_DIGITS.sub(
            lambda m: cls._mask_value_str(m.group(0)) if cls._luhn_check(m.group(0)) else m.group(0),
            s,
        )
        s = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "***-**-****", s)

        return s
