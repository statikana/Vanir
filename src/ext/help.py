import re
from asyncio import iscoroutinefunction
from typing import Callable, Any, Coroutine

import discord
from discord import InteractionResponse
from discord.ext import commands

from src.types.command import (
    cog_hidden,
    VanirCog,
    vanir_group,
    AutoCachedView,
    vanir_command,
)
from src.types.core import VanirContext, Vanir
from src.types.util import find_content

from src.util import (
    format_dict,
    discover_cog,
    discover_group,
    get_display_cogs,
    get_param_annotation,
    closest_name,
)


class Help(VanirCog):
    @vanir_group()
    async def help(self, ctx: VanirContext):
        """Stop it, get some help"""

        # Cogs -> Modules
        embed = await self.get_cog_display_embed(ctx)
        sel = CogDisplaySelect(ctx, self)

        view = AutoCachedView(user=ctx.author, items=[sel])

        await ctx.reply(embed=embed, view=view)

    @vanir_command()
    @commands.cooldown(2, 60, commands.BucketType.user)
    async def snowflake(self, ctx: VanirContext, snowflake: str):
        regex = re.compile(r"^[0-9]{15,20}$")
        if not regex.fullmatch(snowflake):
            raise ValueError("Not a snowflake.")
            # check cache first
        sf = int(snowflake)

        cache_attributes = ("user", "channel", "guild", "role" "emoji", "sticker")

        fetch_attributes = ("message", "user", "channel", "role")

        for cache_attr in cache_attributes:
            if await self.scan_methods(ctx, "get", cache_attr, sf):
                break
        else:
            for fetch_attr in fetch_attributes:
                if await self.scan_methods(ctx, "fetch", fetch_attr, sf):
                    break

        embed = await self.snowflake_info_embed(ctx, sf)

    async def scan_methods(
        self, ctx: VanirContext, method: str, attr: str, snowflake: int
    ):
        try:
            func = getattr(ctx.guild, f"{method}_{attr}")
            received = await self.maybecoro_get(func, snowflake)
        except AttributeError:
            func = getattr(self.bot, f"{method}_{attr}")
            received = await self.maybecoro_get(func, snowflake)

        if received is None:
            return False

        embed = await getattr(self, f"{attr}_info_embed")(ctx, received)
        await ctx.reply(embed=embed)
        return True

    async def maybecoro_get(self, method: Callable[[int], ...], snowflake: int):
        if iscoroutinefunction(method):
            received = await method(snowflake)
        else:
            received = method(snowflake)
        return received

    async def user_info_embed(self, ctx: VanirContext, user: discord.User):
        member = ctx.guild.get_member_named(user.name)
        embed = ctx.embed(title=f"{user.name}", description=f"ID: `{user.id}`")
        created_ts = int(user.created_at.timestamp())
        embed.add_field(
            name="Created At",
            value=f"<t:{created_ts}:T> [<t:{created_ts}:R>]",
            inline=False,
        )
        embed.add_field(
            name=f"Mutual Guilds [`{len(user.mutual_guilds)}`]",
            value=f"\n".join(
                f"- {guild.name} [ID: `{guild.id}`]" for guild in user.mutual_guilds[:7]
            ),
            inline=False,
        )
        data = {
            "Is Bot": user.bot,
            "Is System": user.system,
        }

        if member is not None:
            data.update({"Color": closest_name(str(member.color)[1:])[0].title()})

        embed.add_field(name="Misc. Data", value=format_dict(data), inline=False)

        if member is not None:
            embed.add_field(
                name="Roles",
                value=f"{len(member.roles) - 1} Total\nTop: {' '.join(r.mention for r in sorted(filter(lambda r: r.name != '@everyone', member.roles), key=lambda r: r.permissions.value, reverse=True)[:3])}",
            )
        # discord.Permissions.value
        await self.add_sf_data(embed, user.id)
        return embed

    async def snowflake_info_embed(self, ctx: VanirContext, snowflake: int):
        embed = ctx.embed("No Object Found")
        await self.add_sf_data(embed, snowflake)
        return embed

    async def add_sf_data(self, embed: discord.Embed, snowflake: int):
        time = int(discord.utils.snowflake_time(snowflake).timestamp())
        as_bin = str(bin(snowflake))
        generation, process, worker = (
            int(as_bin[:12], 2),
            int(as_bin[12:17], 2),
            int(as_bin[17:22], 2),
        )
        data = {
            "Created At": f"<t:{time}:T> [<t:{time}:R>]",
            "Worker ID": f"`{worker}`",
            "Process ID": f"`{process}`",
            "SF Generation ID": f"`{generation}`",
        }

        embed.add_field(name="Snowflake Info", value=format_dict(data))

    async def get_cog_display_embed(self, ctx: VanirContext) -> discord.Embed:
        embed = ctx.embed(
            title="Module Select",
        )

        cogs = get_display_cogs(self.bot)
        for c in cogs:
            embed.add_field(
                name=c.qualified_name,
                value=f"*{c.description or 'No Description'}*",
                inline=True,
            )

        return embed

    async def get_cog_info_embed(
        self, itx: discord.Interaction, cog: commands.Cog
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f"Module Info: **{cog.qualified_name}**",
            description=f"*{cog.description or 'No Description'}*",
            author=itx.user,
        )

        other_commands: list[commands.Command] = []

        for c in cog.get_commands():
            if isinstance(c, commands.Group):
                embed.add_field(
                    name=f"`{c.qualified_name}` Commands",
                    value="\n".join(
                        f"`/{sub.qualified_name}`" for sub in discover_group(c)
                    ),
                )
            else:
                other_commands.append(c)

        if other_commands:
            embed.add_field(
                name=f"{len(other_commands)} Miscellaneous Command{'s' if len(other_commands) > 1 else ''}",
                value="\n".join(f"`/{o.qualified_name}`" for o in other_commands),
            )

        return embed

    async def get_command_info_embed(
        self, itx: discord.Interaction, command: commands.Command
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f"Info: `/{command.qualified_name} {command.signature}`",
            description=f"*{command.description or command.short_doc or 'No Description'}*",
            author=itx.user,
        )

        for name, param in command.params.items():
            data = {"Required": "Yes" if param.required else "No"}
            if not param.required:
                data["Default"] = param.displayed_default or param.default
            embed.add_field(
                name=f"__`{name}`__: `{get_param_annotation(param)}`",
                value=f"*{param.description}*\n{format_dict(data)}",
                inline=False,
            )

        return embed

    async def get_command_info_select(
        self, ctx: VanirContext, command: commands.Command
    ):
        return CogInfoSelect(ctx, self, command.cog)


class CogDisplaySelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays all cogs in the bot"""

    def __init__(self, ctx: VanirContext, instance: Help):
        self.ctx = ctx
        self.instance = instance
        options = [
            discord.SelectOption(
                label=c.qualified_name,
                description=c.description or "No Description",
                value=c.qualified_name,
                emoji=getattr(c, "emoji", "\N{Black Question Mark Ornament}"),
            )
            for c in get_display_cogs(self.ctx.bot)
        ]
        super().__init__(options=options, placeholder="Select a Module", row=0)

    async def callback(self, itx: discord.Interaction):
        """Goes to `cog info`"""
        # print("COG DISPLAY SELECT cb")
        await self.view.collect(itx)
        selected = self.values[0]
        cog = self.ctx.bot.get_cog(selected)

        embed = await self.instance.get_cog_info_embed(itx, cog)
        sel = CogInfoSelect(self.ctx, self.instance, cog)

        self.view.remove_item(self)
        self.view.add_item(sel)

        await InteractionResponse(itx).defer()
        await itx.message.edit(embed=embed, view=self.view)


class CogInfoSelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays commands in a cog"""

    def __init__(self, ctx: VanirContext, instance: Help, cog: commands.Cog):
        self.ctx = ctx
        self.instance = instance
        options = [
            discord.SelectOption(
                label=c.qualified_name,
                description=f"{c.description or c.short_doc or 'No Description'}",
                value=c.qualified_name,
            )
            for c in discover_cog(cog)
        ]
        super().__init__(options=options, placeholder="Select a Command", row=0)

    async def callback(self, itx: discord.Interaction):
        """Goes to `command info`"""
        await self.view.collect(itx)
        selected = self.values[0]
        command = self.ctx.bot.get_command(selected)

        embed = await self.instance.get_command_info_embed(itx, command)
        sel = await self.instance.get_command_info_select(self.ctx, command)

        self.view.remove_item(self)
        self.view.add_item(sel)

        await InteractionResponse(itx).defer()
        await itx.message.edit(embed=embed, view=self.view)


async def setup(bot: Vanir):
    await bot.add_cog(Help(bot))
