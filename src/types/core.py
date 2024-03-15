from typing import Any
from src.ext import MODULE_PATHS

import aiohttp
import asyncpg
import discord
from discord.ext import commands


from src import env
from src.env import DEEPL_API_KEY
from src.types.database import StarBoard, Currency, Todo, TLink, TLINK


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
        self.db_todo = Todo()
        self.db_link = TLink()
        self.session: VanirSession = VanirSession()

        self.cache: BotCache = BotCache()

        self.launch_time = discord.utils.utcnow()

    async def get_context(
        self,
        origin: discord.Message | discord.Interaction,
        /,
        *,
        cls: Any = None,
    ) -> "VanirContext":
        return await super().get_context(origin, cls=VanirContext)

    async def setup_hook(self) -> None:

        pool = await asyncpg.create_pool(**env.PSQL_CONNECTION)
        self.db_starboard.start(pool)
        self.db_currency.start(pool)
        self.db_todo.start(pool)
        self.db_link.start(pool)

        await self.cache.init()
        await self.add_cogs()

    async def add_cogs(self):
        for ext in MODULE_PATHS:
            await self.load_extension(ext)

        await self.load_extension("jishaku")


class VanirTree(discord.app_commands.CommandTree):
    def __init__(self, client: discord.Client) -> None:
        super().__init__(client=client, fallback_to_global=True)


class VanirContext(commands.Context):
    bot: Vanir

    def embed(
        self,
        title: str | None = None,
        description: str | None = None,
        color: discord.Color = None,
        url: str | None = None,
    ) -> discord.Embed:
        if color is None:
            if isinstance(self.author, discord.Member):
                color = self.author.top_role.color
            else:
                color = discord.Color.light_embed()

        embed = discord.Embed(title=title, description=description, color=color)

        embed.set_author(
            name=f"{self.author.global_name or self.author.name}",
            icon_url=self.author.display_avatar.url,
        )

        if url is not None:
            embed.url = url
        return embed

    @staticmethod
    def syn_embed(
        title: str | None = None,
        description: str | None = None,
        color: discord.Color = None,
        url: str | None = None,
        *,
        user: discord.User | discord.Member,
    ) -> discord.Embed:
        if color is None:
            if isinstance(user, discord.Member):
                color = user.top_role.color
            else:
                color = discord.Color.light_embed()

        embed = discord.Embed(title=title, description=description, color=color)

        # %B %-d, %H:%M -> September 8, 13:59 UTC
        embed.set_author(
            name=f"{user.global_name or user.name}",
            icon_url=user.display_avatar.url,
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


class BotCache:
    def __init__(self, bot: Vanir):
        self.bot = bot
        self.tlinks: list[TLink] = []
    
    async def init(self):
        self.tlinks = await self.bot.db_link.get_all_links()