import datetime
import os
from typing import Generator

import discord
from discord.ext import commands

import logging


class Charm(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=None, tree_cls=CharmTree, intents=discord.Intents.none()
        )

    async def setup_hook(self) -> None:
        # Load all cogs in `./src/ext` extension files
        async for cog in self.add_cogs():
            logging.info(f"Loaded {cog.qualified_name}")

    async def add_cogs(self) -> Generator[commands.Cog]:
        extension_path = ".\\src\\ext"
        for path in os.listdir(extension_path):
            if path.endswith(".py"):
                before = set(self.cogs)
                await self.load_extension(path)
                after = set(self.cogs)
                for ext in after - before:
                    yield ext


class CharmTree(discord.app_commands.CommandTree):
    def __init__(self):
        super().__init__(client=type[Charm], fallback_to_global=True)


class CharmContext(commands.Context):
    def embed(
        self,
        title: str | None,
        description: str | None = None,
        color: discord.Color = discord.Color.dark_teal(),
    ) -> discord.Embed:
        if title is None and description is None:
            raise ValueError("Must provide either a title or a description")

        embed = discord.Embed(title=title, description=description, color=color)

        # %B %-d, %H:%M -> September 8, 13:59 UTC
        embed.set_footer(
            text=f"{self.author.global_name or self.author.name} @ {datetime.datetime.utcnow().strftime('%B %-d, %H:%M')} UTC",
            icon_url=self.author.display_icon.url,
        )

        return embed
