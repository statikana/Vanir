from __future__ import annotations

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
from src.util.format import fmt_dict
from src.util.parse import fuzzysearch


@cog_hidden
class Help(VanirCog):
    @vanir_command()
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def help(
        self,
        ctx: VanirContext,
        *,
        thing: BotObjectT | None = commands.param(
            description="The thing to get help on",
            converter=BotObjectConverter(),
            default=None,
        ),
    ) -> None:
        """Stop it, get some help."""
        # Cogs -> Modules
        if isinstance(thing, commands.Cog):
            embed = await self.cog_details_embed(thing, ctx.author)
            view = AutoCachedView(self.bot, user=ctx.author)
            display_sel = CogDisplaySelect(ctx, self)
            for item in display_sel.options:
                item.default = item.value == thing.qualified_name
            view.auto_add_item(display_sel)

        elif isinstance(thing, VanirHybridGroup):
            embed = await self.group_details_embed(thing, ctx.author)
            view = AutoCachedView(self.bot, user=ctx.author)
            display_sel = CogDisplaySelect(ctx, self)
            for item in display_sel.options:
                item.default = item.value == thing.cog.qualified_name
            view.auto_add_item(display_sel)

            detail_sel = GroupDetailSelect(ctx, self, thing)
            for item in detail_sel.options:
                item.default = item.value == thing.qualified_name
            detail_sel.row = 1
            view.auto_add_item(detail_sel)

        elif isinstance(thing, commands.Command):
            embed = await self.command_details_embed(thing, ctx.author)
            view = AutoCachedView(self.bot, user=ctx.author)
            display_sel = CogDisplaySelect(ctx, self)
            for item in display_sel.options:
                item.default = item.value == thing.cog.qualified_name
            view.auto_add_item(display_sel)

            detail_sel = CogDetailSelect(ctx, self, thing.cog)
            for item in detail_sel.options:
                item.default = item.value == thing.qualified_name
            detail_sel.row = 1
            view.auto_add_item(detail_sel)

        else:
            embed = await self.main_page_embed(ctx.author)
            sel = CogDisplaySelect(ctx, self)

            view = AutoCachedView(self.bot, user=ctx.author, items=[sel])

        await ctx.reply(embed=embed, view=view)

    async def main_page_embed(self, user: discord.User) -> discord.Embed:
        description = (
            "Vanir is a multi-purpose bot with a variety of features. It is also still in development, so "
            "expect some bugs!"
        )

        getting_help = (
            "If you need help with a specific command, you can use the `\\help <command name>` "
            "command to get more information on what it does and how to use it. "
            "You can also use the drop-down menu below to select a module to get more information on."
        )
        contacting = (
            "If you encounter any bugs or issues, please use `\\bug` to report it to the developers (me!). "
            "If you have any suggestions or feedback, you can use `\\suggest` to send it to me as well. "
            "If you just want to talk, you can also send an email to me at `contact@statikana.dev`."
        )

        embed = VanirContext.syn_embed(
            title="Vanir Help Menu",
            description=description,
            user=user,
        )
        embed.add_field(
            name="\N{WHITE QUESTION MARK ORNAMENT} Getting Help",
            value=getting_help,
            inline=False,
        )
        embed.add_field(
            name="\N{ENVELOPE WITH DOWNWARDS ARROW ABOVE} Contacting the Developers",
            value=contacting,
            inline=False,
        )
        return embed

    async def cog_display_embed(self, user: discord.User) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title="Module Select",
            user=user,
        )

        cogs = get_display_cogs(self.bot)
        for c in cogs:
            embed.add_field(
                name=f"{c.emoji} {c.qualified_name}",
                value=f"*{c.description or 'No Description'}*",
                inline=True,
            )

        return embed

    async def cog_details_embed(
        self,
        cog: commands.Cog,
        user: discord.User,
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f":information_source: **{cog.qualified_name}**",
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
        self,
        group: VanirHybridGroup,
        user: discord.User,
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f":information_source: **{group.qualified_name}**",
            description=f"*{group.short_doc}*",
            user=user,
        )

        for c in discover_group(group):
            embed.description += f"\n`\\{c.qualified_name}`\n➥*{c.short_doc}*"

        return embed

    async def command_details_embed(
        self,
        command: commands.Command,
        user: discord.User,
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
            title=f":information_source: `\\{command.qualified_name} {command.signature}`",
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
        all_values: list[tuple[str, str]] = []
        all_values.extend(
            ("Module", cog.qualified_name) for cog in get_display_cogs(self.bot)
        )
        for cmd in self.bot.walk_commands():
            if not cmd.hidden and not cmd.qualified_name.startswith("jishaku"):
                all_values.append(
                    (
                        "Command" if not isinstance(cmd, commands.Group) else "Group",
                        cmd.qualified_name,
                    ),
                )

        all_values = fuzzysearch(thing.lower(), all_values, key=lambda t: t[1].lower())[
            :25
        ]

        return [
            discord.app_commands.Choice(name=f"[{typ}] {ident}", value=ident)
            for typ, ident in all_values
        ]


class CogDisplaySelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays all cogs in the bot."""

    def __init__(self, ctx: VanirContext, instance: Help) -> None:
        self.ctx = ctx
        self.instance = instance
        options = [
            discord.SelectOption(
                label=c.qualified_name,
                description=c.description or "No Description",
                value=c.qualified_name,
                emoji=c.emoji,
            )
            for c in get_display_cogs(self.ctx.bot)
        ]
        options = [
            discord.SelectOption(
                label="Main Page",
                description="Go back to the main page",
                value="return-to-main",
                emoji="🏠",
                default=True,
            ),
            *options,
        ]
        super().__init__(options=options, placeholder="Select a Module", row=0)

    async def callback(self, itx: discord.Interaction) -> None:
        """Goes to `cog info`."""
        await self.view.collect(itx)
        selected = self.values[0]
        if selected == "return-to-main":
            for opt in self.options:
                opt.default = opt.value == selected

            command_select = discord.utils.find(
                lambda x: isinstance(x, discord.ui.Select) and x.row == 1,
                self.view.children,
            )
            if command_select is not None:
                self.view.remove_item(command_select)

            embed = await self.instance.main_page_embed(itx.user)
            await itx.response.edit_message(embed=embed, view=self.view)
            return

        cog = self.ctx.bot.get_cog(selected)

        this: discord.ui.Select = discord.utils.find(
            lambda x: isinstance(x, discord.ui.Select) and x.row == 0,
            self.view.children,
        )

        for opt in this.options:
            opt.default = opt.value == selected

        embed = await self.instance.cog_details_embed(cog, itx.user)

        command_select = discord.utils.find(
            lambda x: isinstance(x, discord.ui.Select) and x.row == 1,
            self.view.children,
        )
        if command_select is not None:
            self.view.remove_item(command_select)
        sel = CogDetailSelect(self.ctx, self.instance, cog)
        sel.row = 1
        self.view.auto_add_item(sel)

        await itx.response.edit_message(embed=embed, view=self.view)


class CogDetailSelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays commands in a cog."""

    def __init__(self, ctx: VanirContext, instance: Help, cog: VanirCog) -> None:
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
        options.insert(
            0,
            # back to cog display
            discord.SelectOption(
                label=cog.qualified_name,
                description=f"Go back to the {cog.qualified_name} page",
                emoji=cog.emoji,
                value=f"return:{cog.qualified_name}",
            ),
        )
        super().__init__(options=options, placeholder="Select a Command", row=0)

    async def callback(self, itx: discord.Interaction) -> None:
        """Goes to `command info`."""
        await self.view.collect(itx)
        if self.values[0].startswith("return:"):
            cog_name = self.values[0].split(":")[1]
            cog = self.ctx.bot.get_cog(cog_name)
            embed = await self.instance.cog_details_embed(cog, itx.user)

            for opt in self.options:
                opt.default = False

            await itx.response.edit_message(embed=embed, view=self.view)
            return

        command = self.ctx.bot.get_command(self.values[0])

        embed = await self.instance.command_details_embed(command, itx.user)
        this: discord.ui.Select = discord.utils.find(
            lambda x: isinstance(x, discord.ui.Select) and x.row == 1,
            self.view.children,
        )
        for opt in this.options:
            opt.default = opt.value == self.values[0]

        await itx.response.edit_message(embed=embed, view=self.view)


class GroupDetailSelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays commands in a group."""

    def __init__(
        self,
        ctx: VanirContext,
        instance: Help,
        group: VanirHybridGroup,
    ) -> None:
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

    async def callback(self, itx: discord.Interaction) -> None:
        """Goes to `command info`."""
        await self.view.collect(itx)

        command = self.ctx.bot.get_command(self.values[0])

        embed = await self.instance.command_details_embed(command, itx.user)
        this = discord.utils.find(
            lambda x: isinstance(x, discord.ui.Select) and x.row == 1,
            self.view.children,
        )
        for opt in this.options:
            opt.default = opt.value == self.values[0]

        await itx.response.edit_message(embed=embed, view=self.view)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Help(bot))
