from __future__ import annotations

import time
from asyncio import iscoroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    import discord


@dataclass
class MessageState:
    content: str
    embeds: list[discord.Embed]
    items: list[discord.ui.Item]

    def __str__(self) -> str:
        return (
            f"{self.content or '_'} - {','.join(e.title for e in self.embeds)} - "
            f"{len(self.items)} children"
        )

    def __repr__(self) -> str:
        return self.__str__()


async def timed(func: Callable, *args: Any) -> float:
    start = time.time()
    result = func(*args)

    if iscoroutine(result):
        await result

    return time.time() - start
