"""
Code is partially from R. Danny by Rapptz.

It has been modified to fit the needs of Vanir.
https://github.com/Rapptz/RoboDanny/blob/677012bc26e80ddb19f11d853f8113458b8fe726/cogs/utils/time.py.
"""

from __future__ import annotations

import datetime
import re
import time
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta
from discord.ext import commands

from src.constants import TIME_UNITS
from src.util.format import natural_join
from src.util.regex import SPACE_FORMAT_REGEX, SPACE_SUB_REGEX

if TYPE_CHECKING:
    from src.types.core import VanirContext


class ShortTime:
    compiled = re.compile(
        """
           (?:(?P<years>-?[0-9]*)(?:years?|y))?
           (?:(?P<months>-?[0-9]*)(?:months?|mon?))?
           (?:(?P<weeks>-?[0-9]*)(?:weeks?|w))?
           (?:(?P<days>-?[0-9]*)(?:days?|d))?
           (?:(?P<hours>-?[0-9]*)(?:hours?|hr?s?))?
           (?:(?P<minutes>-?[0-9]*)(?:minutes?|m(?:ins?)?))?
           (?:(?P<seconds>-?[0-9]*)(?:seconds?|s(?:ecs?)?))?
        """,
        re.VERBOSE,
    )

    discord_fmt = re.compile(r"<t:(?P<ts>[0-9]+)(?:\:?[RFfDdTt])?>")

    dt: datetime.datetime

    def __init__(
        self,
        argument: str,
        *,
        now: datetime.datetime | None = None,
        tzinfo: datetime.tzinfo = datetime.timezone.utc,
    ) -> None:
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            match = self.discord_fmt.fullmatch(argument)
            if match is not None:
                self.dt = datetime.datetime.fromtimestamp(
                    int(match.group("ts")),
                    tz=datetime.timezone.utc,
                )
                if tzinfo is not datetime.timezone.utc:
                    self.dt = self.dt.astimezone(tzinfo)
                return
            else:
                msg = "invalid time provided"
                raise commands.BadArgument(msg)

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or datetime.datetime.now(datetime.timezone.utc)
        self.dt = now + relativedelta(**data)
        if tzinfo is not datetime.timezone.utc:
            self.dt = self.dt.astimezone(tzinfo)

    @classmethod
    async def convert(cls, ctx: VanirContext, argument: str) -> ShortTime:
        return cls(argument, now=ctx.message.created_at)


def format_time(ts: float, from_ts: bool = True) -> str:
    if from_ts:
        ts = int(ts) - int(time.time())
    ts = int(ts)
    desc: dict[str, int] = {}
    for name, length in TIME_UNITS.items():
        n = int(ts / length)  # // is weird for negative numbers
        desc[name] = n
        ts -= length * n

    return (
        natural_join(
            f"{round(abs(v))} {k[:-1] if v == 1 else k}" for k, v in desc.items() if v
        )
        or "0 seconds"
    )


def parse_time(
    expr: str, tz: datetime.timezone | None = datetime.UTC
) -> datetime.datetime:
    string = re.sub(SPACE_FORMAT_REGEX, SPACE_SUB_REGEX, expr)
    diff = sum(ShortTime(part).dt.timestamp() - time.time() for part in string.split())
    ts = diff + time.time()
    return datetime.datetime.fromtimestamp(ts, tz=tz)
