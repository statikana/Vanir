import sys

import logbook
from logbook import Logger, LogRecord

from src.constants import ANSI

book = Logger("vanir")


class VanirFormatter(logbook.StreamHandler):
    def __init__(self):
        super().__init__(sys.stdout, level=logbook.INFO)

    def format(self, record: LogRecord) -> str:
        time = f"{record.time:%X}"
        level = f"{record.level_name:7}".lower()
        level_color = {
            "debug": ANSI["grey"],
            "info": ANSI["green"],
            "warning": ANSI["yellow"],
            "error": ANSI["red"],
            "critical": ANSI["red"],
        }.get(record.level_name.lower(), ANSI["reset"])

        thread = f"{record.thread_name}"
        message = record.message
        return f"{ANSI['grey']}{time} {ANSI['reset']}[{level_color}{level}{ANSI['reset']}] {ANSI['white']}{message}"


book.handlers.append(VanirFormatter())
book.info("Vanir logging initialized", logger=book)
