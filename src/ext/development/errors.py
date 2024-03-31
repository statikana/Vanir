from __future__ import annotations

import contextlib
import traceback
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from src.constants import EMOJIS
from src.logging import book
from src.types.command import (
    CloseButton,
    VanirCog,
    VanirView,
)
from src.types.core import Vanir, VanirContext
from src.util.command import cog_hidden
from src.util.parse import fuzzysearch

if TYPE_CHECKING:
    from src.ext.help import Help


@cog_hidden
class Errors(VanirCog):
    @commands.Cog.listener()
    async def on_command_error(
        self,
        source: VanirContext | discord.Interaction,
        error: commands.CommandError,
    ) -> None:
        try:
            raise error
        except Exception:  # noqa: BLE001
            if error.__cause__ is None:
                tb = "".join(
                    traceback.format_exception(type(error), error, error.__traceback__),
                )
            else:
                traceback_chain = traceback.extract_tb(error.__cause__.__traceback__)
                tb = "".join(traceback.format_list(traceback_chain))
                tb += f"\n{error.__cause__.__class__.__name__}: {error.__cause__}"

        if self.bot.debug and not isinstance(error, commands.CommandNotFound):
            name = source.command.qualified_name if source.command else "<NONE>"
            book.error(
                f"Error in {name} command\n{tb}",
            )
            if isinstance(source, VanirContext):
                await source.reply(
                    embed=discord.Embed(
                        title="An error occurred while processing this command",
                        description=f"```{tb}```",
                        color=discord.Color.red(),
                    ),
                )
            else:
                try:
                    await source.response.send_message(
                        embed=discord.Embed(
                            title="An error occurred while processing this command",
                            description=f"```{tb}```",
                            color=discord.Color.red(),
                        ),
                    )
                except discord.InteractionResponded:
                    await source.followup.send(
                        embed=discord.Embed(
                            title="An error occurred while processing this command",
                            description=f"```{tb}```",
                            color=discord.Color.red(),
                        ),
                    )
            return None

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(
            error,
            (commands.NotOwner,),
        ):
            return None

        user = source.author if isinstance(source, VanirContext) else source.user
        view = ErrorView(source, self.bot, source.command)

        view.add_item(GetTBButton(tb))

        if isinstance(error, commands.CommandNotFound):
            return await self.on_command_not_found(source, error)

        if isinstance(error, commands.MissingRequiredArgument):
            view.add_item(GetHelpButton())

        if isinstance(error, commands.NSFWChannelRequired):
            button = SetNSFWButton()
            if not (
                source.channel.permissions_for(source.guild.me).manage_channels
                and source.channel.permissions_for(user).manage_channels
            ):
                button.disabled = True
            view.add_item(SetNSFWButton())

        title = f"Error - `{type(error).__name__}`"
        color = discord.Color.red()

        embed = VanirContext.syn_embed(
            title=title,
            description=str(error)
            or error.__class__.__doc__
            or "No error description - report with `\\bug`",
            color=color,
            user=user,
        )
        if isinstance(source, discord.Interaction):
            with contextlib.suppress(ValueError):
                source = await VanirContext.from_interaction(source)

        if isinstance(source, VanirContext):
            await source.reply(embed=embed, view=view, ephemeral=True)
            return None
        else:
            try:
                await source.response.send_message(embed=embed, view=view)
            except discord.InteractionResponded:
                await source.followup.send(embed=embed, view=view)

    async def on_command_not_found(
        self,
        source: VanirContext | discord.Interaction,
        error: commands.CommandNotFound,
    ) -> None:
        user = source.author if isinstance(source, VanirContext) else source.user
        commands = self.bot.walk_commands()
        results = fuzzysearch(
            source.message.content[1:],
            [
                cmd
                for cmd in commands
                if not cmd.hidden and not cmd.qualified_name.startswith("jishaku")
            ],
            key=lambda c: c.qualified_name,
            threshold=60,
        )
        if not results:
            return await source.message.add_reaction("\N{WHITE QUESTION MARK ORNAMENT}")

        command = results[0]

        embed = VanirContext.syn_embed(
            description=f"I don't know that command.\nDid you mean `\\{command.qualified_name}`?\n>>> *{command.short_doc}*",
            user=user,
            color=discord.Color.red(),
        )
        if isinstance(source, discord.Interaction):
            with contextlib.suppress(ValueError):
                source = VanirContext.from_interaction(source)

        if isinstance(source, VanirContext):
            view = CommandNotFoundHelper(source, command)
        else:
            view = None
        await source.reply(embed=embed, view=view, ephemeral=True)
        return None


class CommandNotFoundHelper(VanirView):
    def __init__(self, ctx: VanirContext, command: commands.Command) -> None:
        super().__init__(bot=ctx.bot, user=ctx.author)
        self.ctx = ctx
        self.command = command

        self.add_item(CloseButton())

    @discord.ui.button(
        label="Run",
        emoji=str(EMOJIS["execute"]),
        style=discord.ButtonStyle.success,
    )
    async def run_command(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await itx.message.delete()
        previous = self.ctx.message.content.split()
        new = self.command.qualified_name.split()

        previous[: len(new)] = new

        fixed_content = " ".join(previous)
        prefixes = await self.ctx.bot.get_prefix(self.ctx.message)

        prefix = prefixes if isinstance(prefixes, str) else prefixes[0]

        self.ctx.message.content = f"{prefix}{fixed_content}"
        await self.ctx.bot.process_commands(self.ctx.message)

    @discord.ui.button(
        label="Help",
        emoji=str(EMOJIS["info"]),
        style=discord.ButtonStyle.blurple,
    )
    async def get_help(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        instance: Help = self.ctx.bot.get_cog("Help")
        await self.ctx.invoke(instance.help, thing=self.command)
        await itx.response.defer()


class ErrorView(VanirView):
    def __init__(
        self,
        source: VanirContext | discord.Interaction,
        bot: Vanir,
        command: commands.Command,
    ) -> None:
        super().__init__(bot=bot)
        self.source = source
        self.user = source.author if isinstance(source, VanirContext) else source.user
        self.command = command


class GetHelpButton(discord.ui.Button[ErrorView]):
    def __init__(self) -> None:
        super().__init__(
            label="Get Help",
            style=discord.ButtonStyle.primary,
            emoji="\N{WHITE QUESTION MARK ORNAMENT}",
        )
        self.instance: Help

    async def callback(self, itx: discord.Interaction) -> None:
        self.instance: Help = self.view.bot.get_cog("Help")
        embed = await self.instance.command_details_embed(
            self.view.command, self.view.user
        )
        await itx.response.edit_message(embed=embed, view=None)


class SetNSFWButton(discord.ui.Button[ErrorView]):
    def __init__(self) -> None:
        super().__init__(
            label="Set NSFW",
            style=discord.ButtonStyle.danger,
            emoji="\N{NO ONE UNDER EIGHTEEN SYMBOL}",
        )

    async def callback(self, itx: discord.Interaction) -> None:
        await self.view.source.channel.edit(nsfw=True)
        await itx.response.send_message("Channel set to NSFW", ephemeral=True)


class GetTBButton(discord.ui.Button[ErrorView]):
    def __init__(self, tb: str) -> None:
        super().__init__(
            label="Get Traceback",
            style=discord.ButtonStyle.secondary,
            emoji="\N{SCROLL}",
        )
        self.tb = tb

    async def callback(self, itx: discord.Interaction) -> None:
        embed = VanirContext.syn_embed(
            title="Traceback",
            description=f"```{self.tb}```",
            user=self.view.user,
            color=discord.Color.red(),
        )
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Errors(bot))
