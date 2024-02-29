import datetime
import os
from typing import Generator, Any

import aiohttp
import asyncpg
import discord
from discord.ext import commands

import logging

from src import env
from src.env import DEEPL_API_KEY
from src.types.database import StarBoard, Currency


class Vanir(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or("\\"),
            tree_cls=VanirTree,
            intents=discord.Intents.all(),
            help_command=None,
            max_messages=5000,
        )
        self.db_starboard = StarBoard()
        self.db_currency = Currency()
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

        connection = await asyncpg.connect(**env.PSQL_CONNECTION)
        self.db_starboard.start(connection)
        self.db_currency.start(connection)

    async def add_cogs(self) -> Generator[commands.Cog, None, None]:
        extension_path = "./src/ext"
        for path in os.listdir(extension_path):

            if path.endswith(".py"):
                before = set(self.cogs.values())
                await self.load_extension(f"src.ext.{path[:-3]}")
                after = set(self.cogs.values())
                for ext in after - before:
                    yield ext
        await self.load_extension("jishaku")


class VanirTree(discord.app_commands.CommandTree):
    def __init__(self, client: discord.Client) -> None:
        super().__init__(client=client, fallback_to_global=True)


class VanirContext(commands.Context):
    bot: Vanir

    def embed(
        self,
        title: str | None,
        description: str | None = None,
        color: discord.Color = None,
        url: str | None = None,
    ) -> discord.Embed:
        if title is None and description is None:
            raise ValueError("Must provide either a title or a description")

        if color is None:
            if isinstance(self.author, discord.Member):
                color = self.author.top_role.color
            else:
                color = discord.Color.light_embed()

        embed = discord.Embed(title=title, description=description, color=color)

        # %B %-d, %H:%M -> September 8, 13:59 UTC
        embed.set_footer(
            text=f"{self.author.global_name or self.author.name} @ {datetime.datetime.utcnow().strftime('%H:%M, %d %b, %Y')} UTC",
            icon_url=self.author.display_avatar.url,
        )

        if url is not None:
            embed.url = url
        return embed

    @staticmethod
    def syn_embed(
        title: str | None,
        description: str | None = None,
        color: discord.Color = None,
        url: str | None = None,
        *,
        author: discord.User | discord.Member,
    ) -> discord.Embed:
        if title is None and description is None:
            raise ValueError("Must provide either a title or a description")

        if color is None:
            if isinstance(author, discord.Member):
                color = author.top_role.color
            else:
                color = discord.Color.light_embed()

        embed = discord.Embed(title=title, description=description, color=color)

        # %B %-d, %H:%M -> September 8, 13:59 UTC
        embed.set_footer(
            text=f"{author.global_name or author.name} @ {datetime.datetime.utcnow().strftime('%H:%M, %d %b, %Y')} UTC",
            icon_url=author.display_avatar.url,
        )

        if url is not None:
            embed.url = url
        return embed


class VanirSession(aiohttp.ClientSession):
    def __init__(self):
        super().__init__(
            raise_for_status=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
            },
        )

    async def deepl(self, path: str, headers: dict = None, json: dict = None):
        if headers is None:
            headers = {}
        if json is None:
            json = {}

        url = "https://api-free.deepl.com/v2"

        headers.update(
            {
                "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}",
                "Content-Type": "application/json ",
            }
        )

        return await self.post(url + path, headers=headers, json=json)
