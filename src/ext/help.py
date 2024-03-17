import discord
from discord.ext import commands

from src.types.command import (
    AutoCachedView,
    BotObjectT,
    VanirCog,
    VanirHybridGroup,
    vanir_command,
)
from src.types.core import Vanir, VanirContext
from src.types.interface import BotObjectConverter
from src.util.command import (
    cog_hidden,
    discover_cog,
    discover_group,
    get_display_cogs,
    get_param_annotation,
)
from src.util.fmt import fmt_dict


@cog_hidden
class Help(VanirCog):
    @vanir_command()
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def help(
        self,
        ctx: VanirContext,
        thing: BotObjectT | None = commands.param(
            description="The thing to get help on",
            converter=BotObjectConverter(),
            default=None,
        ),
    ):
        """Stop it, get some help"""

        # Cogs -> Modules
        if isinstance(thing, commands.Cog):
            embed = await self.cog_details_embed(thing, ctx.author)
            sel = CogDetailSelect(ctx, self, thing)

            view = AutoCachedView(self.bot, user=ctx.author, items=[sel])

            await ctx.reply(embed=embed, view=view)
            return

        if isinstance(thing, VanirHybridGroup):
            embed = await self.group_details_embed(thing, ctx.author)
            sel = GroupDetailSelect(ctx, self, thing)

            view = AutoCachedView(self.bot, user=ctx.author, items=[sel])

            await ctx.reply(embed=embed, view=view)
            return

        if isinstance(thing, commands.Command):
            embed = await self.command_details_embed(thing, ctx.author)
            await ctx.reply(embed=embed, ephemeral=True)
            return

        embed = await self.cog_display_embed(ctx.author)
        sel = CogDisplaySelect(ctx, self)

        view = AutoCachedView(self.bot, user=ctx.author, items=[sel])

        await ctx.reply(embed=embed, view=view)

    async def cog_display_embed(self, user: discord.User) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title="Module Select",
            user=user,
        )

        cogs = get_display_cogs(self.bot)
        for c in cogs:
            embed.add_field(
                name=f"{getattr(c, 'emoji')} {c.qualified_name}",
                value=f"*{c.description or 'No Description'}*",
                inline=True,
            )

        return embed

    async def cog_details_embed(
        self, cog: commands.Cog, user: discord.User
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f"Module Info: **{cog.qualified_name}**",
            description=f"*{cog.description or 'No Description'}*",
            user=user,
        )

        other_commands: list[commands.Command] = []

        for c in cog.get_commands():
            if isinstance(c, commands.Group):
                embed.add_field(
                    name=f"`{c.qualified_name}` Commands",
                    value="\n".join(
                        f"`\\{sub.qualified_name}`\n➥*{sub.short_doc}*"
                        for sub in discover_group(c)
                    ),
                )
            else:
                other_commands.append(c)

        if other_commands:
            embed.add_field(
                name=f"{len(other_commands)} Miscellaneous Command{'s' if len(other_commands) > 1 else ''}",
                value="\n".join(
                    f"`\\{o.qualified_name}`\n➥*{o.short_doc}*" for o in other_commands
                ),
            )

        return embed

    async def group_details_embed(
        self, group: VanirHybridGroup, user: discord.User
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f"Group Info: **{group.qualified_name}**",
            description=f"*{group.description or 'No Description'}*",
            user=user,
        )

        other_commands: list[commands.Command] = []

        for c in group.commands:
            if isinstance(c, commands.Group):
                embed.add_field(
                    name=f"`{c.qualified_name}` Commands",
                    value="\n".join(
                        f"`\\{sub.qualified_name}`\n➥*{sub.short_doc}*"
                        for sub in discover_group(c)
                    ),
                )
            else:
                other_commands.append(c)

        if other_commands:
            embed.add_field(
                name=f"{len(other_commands)} Miscellaneous Command{'s' if len(other_commands) > 1 else ''}",
                value="\n".join(
                    f"`\\{o.qualified_name}`\n➥*{o.short_doc}*" for o in other_commands
                ),
            )

        return embed

    async def command_details_embed(
        self, command: commands.Command, user: discord.User
    ) -> discord.Embed:
        if command.aliases:
            alias_generator = (
                f"`\\{command.full_parent_name}{' ' if command.parent else ''}{c}`"
                for c in command.aliases
            )
            alias_string = f"Aliases: {' '.join(alias_generator)}"
        else:
            alias_string = ""

        embed = VanirContext.syn_embed(
            title=f"Info: `\\{command.qualified_name} {command.signature}`",
            description=f"{alias_string}\n*{command.description or command.short_doc or 'No Description'}*",
            user=user,
        )

        for name, param in command.params.items():
            data = {"Required": "Yes" if param.required else "No"}
            if not param.required:
                data["Default"] = param.displayed_default or param.default
            embed.add_field(
                name=f"__`{name}`__: `{get_param_annotation(param)}`",
                value=f"*{param.description}*\n{fmt_dict(data)}",
                inline=False,
            )

        return embed

    @help.autocomplete("thing")
    async def _thing_autocomplete(self, ctx: VanirContext, thing: str):
        all_values = []
        all_values.extend(cog.qualified_name for cog in get_display_cogs(self.bot))
        all_values.append(
            cmd.qualified_name for cmd in self.bot.walk_commands if not cmd.hidden
        )
        print(all_values)
        return [
            discord.app_commands.Choice(name=ident, value=ident) for ident in all_values
        ]


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
                emoji=getattr(c, "emoji"),
            )
            for c in get_display_cogs(self.ctx.bot)
        ]
        super().__init__(options=options, placeholder="Select a Module", row=0)

    async def callback(self, itx: discord.Interaction):
        """Goes to `cog info`"""
        await self.view.collect(itx)
        selected = self.values[0]
        cog = self.ctx.bot.get_cog(selected)

        embed = await self.instance.cog_details_embed(cog, itx.user)
        sel = CogDetailSelect(self.ctx, self.instance, cog)

        self.view.remove_item(self)
        self.view.add_item(sel)

        await itx.response.edit_message(embed=embed, view=self.view)


class CogDetailSelect(discord.ui.Select[AutoCachedView]):
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
        # we do not collect here because the response is ephemeral
        # so no "progress is lost"

        command = self.ctx.bot.get_command(self.values[0])

        embed = await self.instance.command_details_embed(command, itx.user)

        await itx.response.send_message(embed=embed, ephemeral=True)


class GroupDetailSelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays commands in a group"""

    def __init__(self, ctx: VanirContext, instance: Help, group: VanirHybridGroup):
        self.ctx = ctx
        self.instance = instance
        options = [
            discord.SelectOption(
                label=c.qualified_name,
                description=f"{c.description or c.short_doc or 'No Description'}",
                value=c.qualified_name,
            )
            for c in discover_group(group)
        ]
        super().__init__(options=options, placeholder="Select a Command", row=0)

    async def callback(self, itx: discord.Interaction):
        """Goes to `command info`"""
        # we do not collect here because the response is ephemeral
        # so no "progress is lost"

        command = self.ctx.bot.get_command(self.values[0])

        embed = await self.instance.command_details_embed(command, itx.user)

        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Help(bot))
