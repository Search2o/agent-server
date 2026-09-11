# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ExpectedType(StrEnum):
    intt = "int"
    floatt = "float"
    numbert = "int or float"
    listt = "list"
    dictt = "dict"
    strt = "str"
    boolt = "bool"
    strorintt = "str or int"
    liststrt = "list[str]"
    listnumbert = "list[int] or list[float]"
    dictstrt = "dict[str, Any]"
    listordictt = "list or dict"
    strorliststrt = "str or list[str]"
    strordictstrt = "str or dict[str, Any]"
    anyt = "Any"

class TypeChecker:
    @classmethod
    def check_type(cls, expected_type: ExpectedType, val: Any) -> bool:
        match expected_type:
            case ExpectedType.anyt:
                return True

            case ExpectedType.intt:
                return isinstance(val, int) and not isinstance(val, bool)

            case ExpectedType.floatt:
                return isinstance(val, float)

            case ExpectedType.numbert:
                # (int or float) but not bool
                return isinstance(val, (int, float)) and not isinstance(val, bool)

            case ExpectedType.strt:
                return isinstance(val, str)

            case ExpectedType.boolt:
                return True # All types can be converted to a bool

            case ExpectedType.strorintt:
                return isinstance(val, str) or isinstance(val, int)

            case ExpectedType.listt:
                return isinstance(val, list)

            case ExpectedType.liststrt:
                return isinstance(val, list) and all(isinstance(x, str) for x in val)

            case ExpectedType.listnumbert:
                return isinstance(val, list) and all(
                    (isinstance(x, (int, float)) and not isinstance(x, bool)) for x in val
                )

            case ExpectedType.dictt:
                return isinstance(val, dict)

            case ExpectedType.listordictt:
                return isinstance(val, list) or isinstance(val, dict)

            case ExpectedType.strorliststrt:
                return isinstance(val, str) or (isinstance(val, list) and all(isinstance(x, str) for x in val))

            case ExpectedType.strordictstrt:
                return isinstance(val, str) or (isinstance(val, dict) and all(isinstance(x, str) for x in val.keys()))

            case ExpectedType.dictstrt:
                return isinstance(val, dict) and all(isinstance(k, str) for k in val.keys())
