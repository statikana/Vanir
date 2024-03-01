import time
from asyncio import iscoroutinefunction
from dataclasses import dataclass

import discord
from discord.app_commands import Choice


@dataclass
class MessageState:
    content: str
    embeds: list[discord.Embed]
    items: list[discord.ui.Item]

    def __str__(self):
        return f"{self.content or '_'} -  {','.join(e.title for e in self.embeds)} - {len(self.items)} children"

    def __repr__(self):
        return self.__str__()


async def timed(func, *args):
    start = time.time()
    await func(*args)

    return time.time() - start
