from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import discord  # noqa: TCH002
from discord.ext import commands

from src.constants import LANGUAGE_CODE_MAP, LANGUAGE_CODES
from src.types.command import VanirCog, vanir_group
from src.util.command import safe_default

if TYPE_CHECKING:
    from src.types.core import Vanir, VanirContext


class TLink(VanirCog):
    """Translation Links."""

    emoji = "\N{LINK SYMBOL}"

    @vanir_group()
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    async def tlink(
        self,
        ctx: VanirContext,
        from_channel: discord.TextChannel | None = commands.param(
            description="The channel to translate from",
            default=None,
        ),
        to_channel: discord.TextChannel | None = commands.param(
            description="The channel to translate to",
            default=None,
        ),
        from_lang: str = commands.param(
            description="The language to translate from",
            default="AUTO",
        ),
        to_lang: str = commands.param(
            description="The language to translate to",
            default="EN",
        ),
    ) -> None:
        r"""Links channels together for translation [default: `\tlink list` or `\tlink create ...`]."""
        from_channel = safe_default(from_channel)
        if from_channel is not None:
            if to_channel is None:
                ctx.command = self.create
                raise commands.MissingRequiredArgument(
                    commands.Parameter("to_channel", inspect.Parameter.POSITIONAL_ONLY),
                )
            await ctx.invoke(
                self.create,
                from_channel=from_channel,
                to_channel=safe_default(to_channel),
                from_lang=safe_default(from_lang),
                to_lang=safe_default(to_lang),
            )
        else:
            await ctx.invoke(self.list_)

    @tlink.command()
    async def create(
        self,
        ctx: VanirContext,
        from_channel: discord.TextChannel = commands.param(
            description="The channel to translate from",
        ),
        to_channel: discord.TextChannel = commands.param(
            description="The channel to translate to",
        ),
        from_lang: str = commands.param(
            description="The language to translate from",
            default="AUTO",
        ),
        to_lang: str = commands.param(
            description="The language to translate to",
            default="EN",
        ),
    ) -> None:
        """Adds a translation link between two channels."""
        existing = await self.bot.db_link.get_guild_links(ctx.guild.id)
        if len(existing) >= 10:
            msg = "You can only have 10 translation links per server"
            raise ValueError(msg)

        for link in existing:
            if (
                link["from_channel_id"] == from_channel.id
                and link["to_channel_id"] == to_channel.id
            ):
                msg = "There is already a link between these channels"
                raise ValueError(msg)

        if from_lang != "AUTO":
            from_lang = LANGUAGE_CODE_MAP.get(from_lang.upper(), from_lang.title())
            from_lang_code = LANGUAGE_CODES.get(from_lang)

            if (
                from_lang_code is None
            ):  # here, it *should* be "AUTO" or a valid lang code
                msg = "Invalid from_lang"
                raise ValueError(msg)
        else:
            from_lang_code = "__"  # auto (see events ext)

        to_lang = LANGUAGE_CODE_MAP.get(to_lang.upper(), to_lang.title())
        to_lang_code = LANGUAGE_CODES.get(to_lang)

        if to_lang_code is None:
            msg = "Invalid to_lang"
            raise ValueError(msg)

        tlink = await self.bot.db_link.create(
            guild_id=ctx.guild.id,
            from_channel_id=from_channel.id,
            to_channel_id=to_channel.id,
            from_lang_code=from_lang_code,
            to_lang_code=to_lang_code,
        )
        self.bot.cache.tlinks.append(tlink)

        embed = ctx.embed(title="Translation Link Added")

        embed.add_field(
            name=f"From {from_channel.mention} to {to_channel.mention}",
            value=f"From {from_lang} to {to_lang}",
        )

        await ctx.reply(embed=embed)

    @tlink.command()
    async def remove(
        self,
        ctx: VanirContext,
        from_channel: discord.TextChannel = commands.param(
            description="The source channel to remove from",
        ),
        to_channel: discord.TextChannel | None = commands.param(
            description="The destination channel to remove from",
            default=None,
        ),
    ) -> None:
        """Removes a translation link between two channels."""
        if isinstance(to_channel, commands.Parameter):
            to_channel = None

        links = await self.bot.db_link.get_guild_links(ctx.guild.id)
        filtered = list(
            filter(
                lambda link: link["from_channel_id"] == from_channel.id
                and (link["to_channel_id"] == to_channel.id if to_channel else True),
                links,
            ),
        )
        if not filtered:
            msg = f"No links found from {from_channel.mention} {('to ' + to_channel.mention) if to_channel else ''}"
            raise ValueError(
                msg,
            )

        for link in filtered:
            await self.bot.db_link.remove(
                ctx.guild.id,
                link["from_channel_id"],
                link["to_channel_id"],
            )
            self.bot.cache.tlinks.remove(link)

        embed = ctx.embed(title="Translation Link Removed")
        for link in filtered:
            from_channel = ctx.guild.get_channel(link["from_channel_id"])
            to_channel = ctx.guild.get_channel(link["to_channel_id"])
            embed.add_field(
                name=f"{from_channel.mention} -> {to_channel.mention}",
                value=f"From {LANGUAGE_CODE_MAP.get(link['from_lang_code'], 'AUTO')} to {LANGUAGE_CODE_MAP[link['to_lang_code']]}",
                inline=False,
            )

        await ctx.reply(embed=embed)

    @tlink.command()
    async def clear(self, ctx: VanirContext) -> None:
        """Removes all translation links from the server."""
        links = await self.bot.db_link.get_guild_links(ctx.guild.id)
        if not links:
            msg = "No translation links to remove"
            raise ValueError(msg)

        for link in links:
            await self.bot.db_link.remove(
                ctx.guild.id,
                link["from_channel_id"],
                link["to_channel_id"],
            )
            self.bot.cache.tlinks.remove(link)

        embed = ctx.embed(title="Translation Links Removed")
        for link in links:
            from_channel = ctx.guild.get_channel(link["from_channel_id"])
            to_channel = ctx.guild.get_channel(link["to_channel_id"])
            embed.add_field(
                name=f"{from_channel.mention} -> {to_channel.mention}",
                value=f"From {LANGUAGE_CODE_MAP.get(link['from_lang_code'], 'AUTO')} to {LANGUAGE_CODE_MAP[link['to_lang_code']]}",
                inline=False,
            )

        await ctx.reply(embed=embed)

    @tlink.command(name="list", aliases=["ls", "all"])
    async def list_(self, ctx: VanirContext) -> None:
        """Lists all translation links on the server."""
        links = await self.bot.db_link.get_guild_links(ctx.guild.id)
        if not links:
            embed = ctx.embed(
                title="No Translation Links",
                description=f"Use `+tlink {self.create.signature}` to create one.",
            )
            return await ctx.reply(embed=embed)

        embed = ctx.embed(title="Translation Links")
        for link in links:
            from_channel = ctx.guild.get_channel(link["from_channel_id"])
            to_channel = ctx.guild.get_channel(link["to_channel_id"])
            embed.add_field(
                name=f"{from_channel.mention} -> {to_channel.mention}",
                value=f"From {LANGUAGE_CODE_MAP.get(link['from_lang_code'], 'AUTO')} to {LANGUAGE_CODE_MAP[link['to_lang_code']]}",
                inline=False,
            )

        await ctx.reply(embed=embed)
        return None


async def setup(bot: Vanir) -> None:
    await bot.add_cog(TLink(bot))
