# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from __future__ import annotations

from html.parser import HTMLParser


class _TagDetector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tag_start: int = 0
        self.tag_end: int = 0
        self.tag_both: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag_start += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tag_both += 1

    def handle_endtag(self, tag: str) -> None:
        self.tag_end += 1



class HtmlChecker:
    @classmethod
    def is_html(cls, text: str) -> bool:
        parser = _TagDetector()
        try:
            parser.feed(text)
            parser.close()
        except Exception:
            # If it completely blows up, treat as non-HTML for safety.
            return False

        return parser.tag_start + parser.tag_both + parser.tag_end > 1
