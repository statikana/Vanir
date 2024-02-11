import datetime
import os
from typing import Generator, Any

import discord
from discord.ext import commands

import logging

from src.types.db_types import StarBoard
from src.types.util_types import VanirSession


class Vanir(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="~~", tree_cls=VanirTree, intents=discord.Intents.all()
        )
        self.db_starboard = None
        self.session: VanirSession = VanirSession()

    async def get_context(
        self,
        origin: discord.Message | discord.Interaction,
        /,
        *,
        cls: Any = None,
    ) -> "VanirContext":
        return await super().get_context(origin, cls=VanirContext)

    async def setup_hook(self) -> None:
        # Load all cogs in `./src/ext` extension files
        async for cog in self.add_cogs():
            logging.info(f"Loaded {cog.qualified_name}")

        self.db_starboard: StarBoard = await StarBoard.create()

    async def add_cogs(self) -> Generator[commands.Cog, None, None]:
        extension_path = ".\\src\\ext"
        for path in os.listdir(extension_path):
            if path.endswith(".py"):
                before = set(self.cogs.values())
                await self.load_extension(f"src.ext.{path[:-3]}")
                after = set(self.cogs.values())
                for ext in after - before:
                    yield ext


class VanirTree(discord.app_commands.CommandTree):
    def __init__(self, client: discord.Client) -> None:
        super().__init__(client=client, fallback_to_global=True)


class VanirContext(commands.Context):
    def embed(
        self,
        title: str | None,
        description: str | None = None,
        color: discord.Color = discord.Color.dark_teal(),
        url: str | None = None,
    ) -> discord.Embed:
        if title is None and description is None:
            raise ValueError("Must provide either a title or a description")

        embed = discord.Embed(title=title, description=description, color=color)

        # %B %-d, %H:%M -> September 8, 13:59 UTC
        embed.set_footer(
            text=f"{self.author.global_name or self.author.name} @ {datetime.datetime.utcnow().strftime('%H:%M, %d %b, %Y')} UTC",
            icon_url=self.author.display_avatar.url,
        )

        if url is not None:
            embed.url = url
        return embed
