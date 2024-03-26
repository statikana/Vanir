"""
This code is from R. Danny by Rapptz. It has been slightly modified to fit the needs of Vanir.
https://github.com/Rapptz/RoboDanny/blob/677012bc26e80ddb19f11d853f8113458b8fe726/cogs/utils/time.py
"""

from __future__ import annotations

import datetime
import re
import time
from typing import Optional

from dateutil.relativedelta import relativedelta
from discord.ext import commands

from src.constants import TIME_UNITS
from src.types.core import VanirContext
from src.util.format import natural_join


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
        now: Optional[datetime.datetime] = None,
        tzinfo: datetime.tzinfo = datetime.timezone.utc,
    ):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            match = self.discord_fmt.fullmatch(argument)
            if match is not None:
                self.dt = datetime.datetime.fromtimestamp(
                    int(match.group("ts")), tz=datetime.timezone.utc
                )
                if tzinfo is not datetime.timezone.utc:
                    self.dt = self.dt.astimezone(tzinfo)
                return
            else:
                raise commands.BadArgument("invalid time provided")

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or datetime.datetime.now(datetime.timezone.utc)
        self.dt = now + relativedelta(**data)
        if tzinfo is not datetime.timezone.utc:
            self.dt = self.dt.astimezone(tzinfo)

    @classmethod
    async def convert(cls, ctx: VanirContext, argument: str):
        return cls(argument, now=ctx.message.created_at)


def regress_time(ts: float):
    ts = int(ts) - int(time.time())
    desc: dict[str, int] = {}
    print(ts)
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
