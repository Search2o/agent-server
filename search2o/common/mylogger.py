# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

import logging


class MyLogger:
    levels = {
        "critical": logging.CRITICAL,
        "fatal": logging.FATAL,
        "error": logging.ERROR,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "debug": logging.DEBUG,
    }

    @classmethod
    def log(cls, name: str | None, level: str | None, message: str) -> None:
        if message:
            logger = logging.getLogger(name) if name else logging.getLogger()
            alevel = cls.levels.get(level, logging.INFO)
            logger.log(alevel, message)


    @classmethod
    def error(cls, message: str) -> None:
        cls.log(None, "error", message)

    @classmethod
    def warning(cls, message: str) -> None:
        cls.log(None, "warning", message)

    @classmethod
    def info(cls, message: str) -> None:
        cls.log(None, "info", message)
