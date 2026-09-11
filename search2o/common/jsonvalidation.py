# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError


class JsonValidator:
    # FastAPI's request-location markers, stripped so a message names the field rather than
    # where it arrived. "query" is NOT here: every route takes a POST body and none declares a
    # query-string parameter, so the word can only ever be a real field name - and it is one,
    # on match and searchCommand, whose errors were losing it.
    SKIP_LOCATIONS = {"body", "path", "header", "cookie"}

    PATTERN_RULES = {
        r"^[A-Za-z][A-Za-z0-9_]*[A-Za-z0-9]$":
            "must start with a letter, end with a letter or a number, and contain only letters, numbers and underscores",
        r"^[A-Za-z][A-Za-z0-9]{1,15}$":
            "must start with a letter and contain only letters and numbers",
        r"^[a-z0-9]+(?:_[a-z0-9]+)*$":
            "may contain only lowercase letters, numbers and underscores, and cannot start or end with an underscore",
        # The same rule where an EMPTY value is also allowed, meaning every tag. A separate
        # entry because the pattern differs, and without one the raw regex reaches the user.
        r"^(?:|[a-z0-9]+(?:_[a-z0-9]+)*)$":
            "may contain only lowercase letters, numbers and underscores, and cannot start or "
            "end with an underscore. Leave it empty to match every tag",
        r"^[0-9A-Za-z]{22}$":
            "must be a 22 character identifier of letters and numbers",
        r"^\{[\x09\x0A\x0D\x20-\x7E]+\}$":
            "must be an expression wrapped in braces, for example { sys.query }",
    }

    # End users see these fields; the raw name is the wrong thing to show them. Everything not
    # listed keeps its field name, which is what a developer editing a request needs.
    FIELD_LABELS = {
        "newPassword": "Your new password",
        "currentPassword": "Your current password",
        "password": "Your password",
        "userName": "Your name",
    }

    PATTERN_HINTS = (
        ("str|int|float|bool|null|any", "must be a type expression such as str, int, list[str] or dict[str, any]"),
    )

    @classmethod
    def field_name(cls, err: dict[str, Any]) -> str:
        parts = []
        for loc in err.get("loc", ()):
            if isinstance(loc, int):
                parts.append(f"item {loc + 1}")
            elif loc in cls.SKIP_LOCATIONS and not parts:
                continue
            else:
                parts.append(str(loc))
        if not parts:
            return ""
        name = parts[0]
        rest = ", ".join(parts[1:])
        return f"{name} ({rest})" if rest else name

    @classmethod
    def pattern_rule(cls, pattern: str) -> str:
        rule = cls.PATTERN_RULES.get(pattern)
        if rule:
            return rule
        for marker, hint in cls.PATTERN_HINTS:
            if marker in pattern:
                return hint
        return "is not in the expected format"

    @classmethod
    def plural(cls, n: Any, word: str) -> str:
        return f"{n} {word}" if str(n) == "1" else f"{n} {word}s"

    @classmethod
    def describe(cls, err: dict[str, Any], field: str) -> str:
        t = err.get("type", "")
        ctx = err.get("ctx") or {}
        subject = cls.FIELD_LABELS.get(field, field) or "The request"
        if "valid email address" in err.get("msg", ""):
            return "Enter a valid email address." if field in ("email", "userEmail") else \
                   f"{subject} must be a valid email address."
        raised = ctx.get("error")
        if raised is not None:
            text = str(raised)
            return text if not field else f"{subject}: {text}"
        match t:
            case "missing":
                return f"{subject} is required."
            case "extra_forbidden":
                return f"{subject} is not a field this request accepts."
            case "string_too_short":
                return f"{subject} must be at least {cls.plural(ctx.get('min_length'), 'character')}."
            case "string_too_long":
                return f"{subject} must be at most {cls.plural(ctx.get('max_length'), 'character')}."
            case "string_pattern_mismatch":
                return f"{subject} {cls.pattern_rule(ctx.get('pattern', ''))}."
            case "too_short":
                return f"{subject} must have at least {cls.plural(ctx.get('min_length'), 'item')}."
            case "too_long":
                return f"{subject} must have at most {cls.plural(ctx.get('max_length'), 'item')}."
            case "greater_than":
                return f"{subject} must be greater than {ctx.get('gt')}."
            case "greater_than_equal":
                return f"{subject} must be at least {ctx.get('ge')}."
            case "less_than":
                return f"{subject} must be less than {ctx.get('lt')}."
            case "less_than_equal":
                return f"{subject} must be at most {ctx.get('le')}."
            case "int_parsing" | "int_type" | "int_from_float":
                return f"{subject} must be a whole number."
            case "float_parsing" | "float_type" | "decimal_parsing":
                return f"{subject} must be a number."
            case "bool_parsing" | "bool_type":
                return f"{subject} must be true or false."
            case "string_type":
                return f"{subject} must be text."
            case "list_type":
                return f"{subject} must be a list."
            case "dict_type" | "model_type":
                return f"{subject} must be an object."
            case "enum" | "literal_error":
                expected = str(ctx.get("expected", "")).replace("'", "")
                return f"{subject} must be one of: {expected}." if expected else f"{subject} is not a permitted value."
            case "json_invalid":
                return "The request body is not valid JSON."
            case _:
                msg = err.get("msg", "is not valid")
                return f"{subject}: {msg}" if field else msg

    @classmethod
    def format_validation_error(cls, exc: ValidationError | RequestValidationError) -> list[str]:
        messages = []
        for err in exc.errors():
            messages.append(cls.describe(err, cls.field_name(err)))
        return messages

    @classmethod
    def error_text(cls, exc: ValidationError | RequestValidationError) -> str:
        return " ".join(cls.format_validation_error(exc))
