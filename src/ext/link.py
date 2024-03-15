import discord
from discord.ext import commands

from types.core import VanirContext
from types.command import VanirCog
from util.command import vanir_command

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
        """
        Live translates messages from one chanel and """
        if isinstance(from_lang, commands.Parameter):
            from_lang = from_lang.default
        if isinstance(to_lang, commands.Parameter):
            to_lang = to_lang.default

        if from_lang != "AUTO":
            from_lang = LANGUAGE_LOOKUP.get(from_lang.title(), from_lang.upper())
            from_lang_code = LANGUAGE_INDEX.get(from_lang)
        
        if from_lang is None:  # here, it *should* be "AUTO" or a valid lang code
            raise ValueError("Invalid from_lang")
                
        to_lang = LANGUAGE_LOOKUP.get(to_lang.title(), to_lang.upper())
        to_lang_code = LANGUAGE_INDEX.get(to_lang)
        if to_lang_code is None:
            raise ValueError("Invalid to_lang")

        tlink = await self.bot.db_link.create(
            guild_id=ctx.guild.id,
            from_channel_id=from_channel.id,
            to_channel_id=to_channel.id,
            from_lang_code=from_lang_code,
            to_lang_code=to_lang_code,
        )
        self.bot.cache.tlinks.append(tlink)

        embed = ctx.embed(
            title="Translation Link Added"
        )

        embed.add_field(
            name=f"From {from_channel.mention} to {to_channel.mention}",
            value=f"From {from_lang} to {to_lang}",
        )

        await ctx.reply(embed=embed)
        