from __future__ import annotations

import datetime
import sys
from logging import LogRecord as BaseLogRecord

import logbook
from logbook import Logger
from logbook import LogRecord as LogbookLogRecord

from src.constants import ANSI

book = Logger("vanir")


class VanirFormatter(logbook.StreamHandler):
    def __init__(self) -> None:
        super().__init__(sys.stdout, level=logbook.INFO)

    def format(self, record: LogbookLogRecord | BaseLogRecord) -> str:
        if isinstance(record, LogbookLogRecord):
            time = f"{record.time:%X}"
            level = f"{record.level_name:7}".lower()
            level_color = {
                "debug": ANSI["grey"],
                "info": ANSI["green"],
                "warning": ANSI["yellow"],
                "error": ANSI["red"],
                "critical": ANSI["red"],
            }[record.level_name.lower()]

            message = record.message
            return f"{ANSI['grey']}{time} {ANSI['reset']}[{level_color}{level}{ANSI['reset']}] {ANSI['white']}{message}"
        elif isinstance(record, BaseLogRecord):
            time = (
                f"{datetime.datetime.fromtimestamp(record.created, tz=datetime.UTC):%X}"
            )
            level = f"{record.levelname:7}".lower()
            level_color = {
                "debug": ANSI["grey"],
                "info": ANSI["green"],
                "warning": ANSI["yellow"],
                "error": ANSI["red"],
                "critical": ANSI["red"],
            }[record.levelname.lower()]
            message = record.getMessage()
            if record.exc_info:
                message += f": {record.exc_info[1]}"

            return f"{ANSI['grey']}{time} {ANSI['reset']}[{level_color}{level}{ANSI['reset']}] {ANSI['red']}[stdlogger] {ANSI['white']}{message}"
        return None


book.handlers.append(VanirFormatter())
book.info("Vanir logging initialized", logger=book)
