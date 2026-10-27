# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.html.

from __future__ import annotations

from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from search2o.models.configtypes import SAFE_EXPR_PATTERN


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
        r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?$":
            "may contain only letters, numbers and the characters _, - and ., and must start "
            "and end with a letter or a number",
        r"^[A-Za-z0-9](?:[A-Za-z0-9_.:/-]*[A-Za-z0-9])?$":
            "may contain only letters, numbers and the characters _, -, ., : and /, and must start "
            "and end with a letter or a number",
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

    # What a value's own type error looks like. When a union member's type does not fit the
    # input, its error says only that - noise beside the error of the member that did fit.
    TYPE_ERRORS = {"string_type": "text", "list_type": "a list", "dict_type": "an object",
                   "model_type": "an object", "model_attributes_type": "an object",
                   "int_type": "a whole number", "float_type": "a number", "bool_type": "true or false",
                   "none_required": "null"}

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
        if t == "string_pattern_mismatch" and ctx.get("pattern") == SAFE_EXPR_PATTERN:
            bad = ", ".join(sorted({c for c in str(err.get("input", ""))
                                   if not (" " <= c <= "~" or c in "\t\r\n")}))
            return (f"{subject} is an expression, which may contain only printable ASCII "
                    f"characters, not {bad}. Inside a string, write such a character as an escape, "
                    f"for example \\u00e9 for é.")
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
            case "union_type":
                return f"{subject} {err['msg']}."
            case "json_invalid":
                return "The request body is not valid JSON."
            case _:
                msg = err.get("msg", "is not valid")
                return f"{subject}: {msg}" if field else msg

    @classmethod
    def format_validation_error(cls, exc: ValidationError | RequestValidationError,
                                data: Any = None) -> list[str]:
        """With `data`, the input that was validated: a value that fails every member of a union
        is reported once, at its own path, by the member its type fits."""
        errors = exc.errors()
        if data is not None:
            errors = cls.without_union_noise([{**err, "loc": cls.input_loc(
                err.get("loc", ()), data, err.get("type") == "missing")} for err in errors])
        return [cls.describe(err, cls.field_name(err)) for err in errors]

    @staticmethod
    def input_loc(loc: tuple, data: Any, missing: bool = False) -> tuple:
        """The location with pydantic's union-member names taken out: only the steps that exist
        in the input are kept - except the last step of a missing error, which is the field that
        is not there."""
        kept, current = [], data
        for step in loc:
            # A dynamic command key (llm.a) is reported in backticks; see CommandBlock.
            key = step.strip("`") if isinstance(step, str) else step
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list) and isinstance(step, int) and 0 <= step < len(current):
                current = current[step]
            else:
                continue
            kept.append(step)
        if missing and loc:
            kept.append(loc[-1])
        return tuple(kept)

    @classmethod
    def without_union_noise(cls, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # An error below a location means some union member fit the value there, so a type
        # mismatch at that location is from a member that did not.
        parents = {err["loc"][:i] for err in errors for i in range(len(err["loc"]))}
        errors = [err for err in errors
                  if not (err.get("type") in cls.TYPE_ERRORS and err["loc"] in parents)]
        by_loc: dict[tuple, list[dict[str, Any]]] = {}
        for err in errors:
            by_loc.setdefault(err["loc"], []).append(err)
        kept = []
        for group in by_loc.values():
            fitting = [err for err in group if err.get("type") not in cls.TYPE_ERRORS]
            if fitting or len(group) == 1:
                kept += fitting or group
                continue
            # No member's type fits: one error naming every type that would.
            kinds = list(dict.fromkeys(cls.TYPE_ERRORS[err["type"]] for err in group))
            kept.append({"loc": group[0]["loc"], "type": "union_type",
                         "msg": f"must be {', '.join(kinds[:-1])} or {kinds[-1]}" if len(kinds) > 1
                         else f"must be {kinds[0]}"})
        return kept

    @classmethod
    def error_text(cls, exc: ValidationError | RequestValidationError, data: Any = None) -> str:
        return " ".join(cls.format_validation_error(exc, data))
