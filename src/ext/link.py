import discord
from discord.ext import commands

from types.core import VanirContext
from types.command import VanirCog
from util.command import vanir_command

from types.interface import langcode_autocomplete
from constants import LANGUAGE_INDEX, LANGUAGE_LOOKUP


class Link(VanirCog):
    @vanir_command()
    async def tlink(
        self,
        ctx: VanirContext,
        from_channel: discord.TextChannel = commands.param(
            description="The channel to translate from"
        ),
        to_channel: discord.TextChannel = commands.param(
            description="The channel to translate to",
        ),
        from_lang: str = commands.param(
            description="The language to translate from", default="AUTO",
        ),
        to_lang: str = commands.param(
            description="The language to translate to", default="EN",
        ),
    ):
        if isinstance(source_lang, commands.Parameter):
            source_lang = source_lang.default
        if isinstance(target_lang, commands.Parameter):
            target_lang = target_lang.default

        if from_lang.title() in LANGUAGE_LOOKUP:
            from_lang = LANGUAGE_LOOKUP[from_lang.title()]
        
        if from_lang.upper() not in LANGUAGE_INDEX:
            raise ValueError(f"Invalid language code: {from_lang}")

        if to_lang.title() in LANGUAGE_LOOKUP:
            to_lang = LANGUAGE_LOOKUP[from_lang.title()]
        
        if to_lang.upper() not in LANGUAGE_INDEX:
            raise ValueError(f"Invalid language code: {to_lang}")
        
        if from_channel.id == to_channel.id:
            raise ValueError("The channels must be different")
        
        if from_lang == to_lang:
            raise ValueError("The languages must be different")

        # good to add
        tlink = await self.bot.db_link.create(
            guild_id=ctx.guild.id,
            from_channel_id=from_channel.id,
            to_channel_id=to_channel.id,
            from_lang=from_lang,
            to_lang=to_lang,
        )
        self.bot.cache.tlinks.append(tlink)

        