from __future__ import annotations

import asyncio
import shutil
from collections import Counter
from dataclasses import dataclass
from typing import Any, TypeVar

import aiofiles
import aiohttp
import asyncpg
import discord
from discord.ext import commands
import wavelink

import config
from src import env
from src.env import DEEPL_API_KEY
from src.ext import MODULE_PATHS
from src.logging import book
from src.logging import main as init_logging
from src.types.orm import TLINK, Currency, DBBase, StarBoard, Status, TLink, Todo
from src.types.piston import PistonORM, PistonRuntime
from src.types.snipe import Buckets, SnipedMessage
from src.util.autocorrect import FuzzyAC, words

SFType = TypeVar(
    "SFType",
    discord.Member,
    discord.Role,
    discord.abc.GuildChannel,
    discord.Emoji,
    discord.Message,
    discord.Guild,
)


class Vanir(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned_or("+"),
            tree_cls=VanirTree,
            intents=discord.Intents.all(),
            help_command=None,
            max_messages=5000,
        )
        self.connect_db_on_init: bool = config.use_system_assets
        self.db_starboard = StarBoard()
        self.db_currency = Currency()
        self.db_todo = Todo()
        self.db_link = TLink()
        self.db_status = Status()
        self.session: VanirSession = VanirSession()

        self.cache: BotCache = BotCache(self)

        self.launch_time = discord.utils.utcnow()

        self.debug: bool = True

        self.piston: PistonORM | None = None
        self.installed_piston_packages: list[PistonRuntime] = []

    async def get_context(
        self,
        origin: discord.Message | discord.Interaction,
        /,
        *,
        cls: Any = None,
    ) -> VanirContext:
        return await super().get_context(origin, cls=VanirContext)

    async def setup_hook(self) -> None:
        init_logging()
        if self.connect_db_on_init:
            book.info("Instantiating database pool and wrappers")
            self.pool = await asyncpg.create_pool(**env.PSQL_CONNECTION)

            if self.pool is None:
                msg = "Could not connect to database"
                raise RuntimeError(msg)

            databases: list[DBBase] = [
                self.db_starboard,
                self.db_currency,
                self.db_todo,
                self.db_link,
                self.db_status,
            ]
            for db in databases:
                db.start(self.pool)

        else:
            book.info("Not connecting to database")

        if config.use_system_assets:
            self.piston = PistonORM(self.session)
            self.installed_piston_packages = await self.piston.runtimes()

        await self.cache.init()
        await self.add_cogs()
        await self.display_shutil()
        await self.create_node()

    async def add_cogs(self) -> None:
        asyncio.gather(*(self.load_extension(ext) for ext in MODULE_PATHS))

        await self.load_extension("jishaku")

    async def add_cog(self, cog: commands.Cog) -> None:
        if config.use_system_assets or not getattr(cog, "uses_sys_assets", False):
            await super().add_cog(cog)
        else:
            book.info(
                f"Skipping {cog.qualified_name} because it requires system assets",
            )

    async def display_shutil(self) -> None:
        resources = [
            "latex",  # pylatex
            "ffmpeg",
            "ffprobe",  # via ffmpeg install
        ]
        for resource in resources:
            if shutil.which(resource) is None:
                book.warning(f"SHUTIL: Could not find {resource} in PATH")
            else:
                book.info(f"SHUTIL: Found {resource} in PATH")

    async def create_node(self) -> None:
        uri = "http://localhost:5678"
        book.info(f"Connecting to Lavalink at {uri}")
        node = wavelink.Node(uri=uri, password="youshallnotpass", client=self)
        await wavelink.Pool.connect(nodes=[node])

    async def dispatch_sf(self, ctx: VanirContext, sf_object: SFType) -> None:
        for command in self.walk_commands():
            if sf_receiver := getattr(command, "sf_receiver", None):
                if issubclass(type(sf_object), sf_receiver):
                    book.info(f"Dispatching {command} for {sf_object}")
                    await ctx.invoke(command, sf_object)


class VanirTree(discord.app_commands.CommandTree):
    def __init__(self, client: discord.Client) -> None:
        super().__init__(client=client, fallback_to_global=True)


class VanirContext(commands.Context):
    bot: Vanir

    def embed(
        self,
        title: str | None = None,
        description: str | None = None,
        color: discord.Color | None = None,
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
        color: discord.Color | None = None,
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
    def __init__(self) -> None:
        super().__init__(
            raise_for_status=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0",
            },
        )

    async def deepl(
        self,
        path: str,
        headers: dict | None = None,
        json: dict | None = None,
    ) -> aiohttp.ClientResponse:
        if headers is None:
            headers = {}
        if json is None:
            json = {}

        url = "https://api-free.deepl.com/v2"

        headers.update(
            {
                "Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}",
                "Content-Type": "application/json ",
            },
        )

        return await self.post(url + path, headers=headers, json=json)


class BotCache:
    def __init__(self, bot: Vanir) -> None:
        self.bot = bot
        self.tlinks: list[TLINK] = []
        self.fuzzy_ac: FuzzyAC | None = None

        # channel id: (source_msg_id, translated_msg_id)
        self.tlink_translated_messages: dict[int, list[TranslatedMessage]] = {}

        self.snipes = Buckets[SnipedMessage](
            30,
            per=lambda snipe: snipe.message.channel.id,
        )

    async def init(self) -> None:
        book.info("Initializing TLink cache")
        if self.bot.connect_db_on_init:
            self.tlinks = await self.bot.db_link.get_all_links()

        async with aiofiles.open("assets/dataset.txt") as file:
            wordset = words(await file.read())
            counter = Counter(wordset)
            self.fuzzy_ac = FuzzyAC(counter)


@dataclass
class TranslatedMessage:
    source_message_id: int
    translated_message_id: int
    source_author_id: int
