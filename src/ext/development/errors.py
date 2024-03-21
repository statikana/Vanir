import traceback

import discord
from discord.ext import commands

from src.constants import EMOJIS
from src.ext.help import Help
from src.logging import book
from src.types.command import (
    CloseButton,
    VanirCog,
    VanirView,
)
from src.types.core import Vanir, VanirContext
from src.util.command import cog_hidden
from src.util.parse import fuzzysearch


@cog_hidden
class Errors(VanirCog):
    @commands.Cog.listener()
    async def on_command_error(
        self, source: VanirContext | discord.Interaction, error: commands.CommandError
    ):
        book.info(f"Handling error in command {source.command}", exc_info=error)
        if self.bot.debug and not isinstance(error, commands.CommandNotFound):
            name = source.command.qualified_name if source.command else "<NONE>"
            try:
                raise error
            except Exception as e:
                book.error(
                    f"Error in {name} command: {e}",
                    exc_info=traceback.format_exc(),
                )
                await source.reply(
                    embed=discord.Embed(
                        title="An error occurred while processing this command",
                        description=f"```{e}```",
                        color=discord.Color.red(),
                    ),
                )
            return

        user = source.author if isinstance(source, VanirContext) else source.user
        view: discord.ui.View | None = None

        if isinstance(error, commands.CommandNotFound):
            return await self.on_command_not_found(source, error)

        if isinstance(error, commands.MissingRequiredArgument):
            instance = self.bot.get_cog("Help")
            view = GetHelpView(self.bot, instance, source.command, user)

        title = f"Error - `{type(error).__name__}`: {error}"
        color = discord.Color.red()

        embed = VanirContext.syn_embed(title=title, color=color, user=source.author)
        await source.reply(embed=embed, view=view, ephemeral=True)

    async def on_command_not_found(
        self,
        source: VanirContext | discord.Interaction,
        error: commands.CommandNotFound,
    ):
        user = source.author if isinstance(source, VanirContext) else source.user
        commands = self.bot.walk_commands()
        results = fuzzysearch(
            source.message.content[1:],
            list(
                cmd
                for cmd in commands
                if not cmd.hidden and not cmd.qualified_name.startswith("jishaku")
            ),
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
            try:
                source = VanirContext.from_interaction(source)
            except ValueError:
                pass

        if isinstance(source, VanirContext):
            view = CommandNotFoundHelper(source, command)
        else:
            view = None

        await source.reply(embed=embed, view=view, ephemeral=True)


class CommandNotFoundHelper(VanirView):
    def __init__(self, ctx: VanirContext, command: commands.Command):
        super().__init__(bot=ctx.bot, user=ctx.author)
        self.ctx = ctx
        self.command = command

        self.add_item(CloseButton())

    @discord.ui.button(
        label="Run",
        emoji=discord.PartialEmoji(name="execute", id=EMOJIS["execute"]),
        style=discord.ButtonStyle.success,
    )
    async def run_command(self, itx: discord.Interaction, button: discord.ui.Button):
        await itx.message.delete()
        previous = self.ctx.message.content.split()
        new = self.command.qualified_name.split()

        previous[: len(new)] = new

        fixed_content = " ".join(previous)
        prefixes = await self.ctx.bot.get_prefix(self.ctx.message)

        if isinstance(prefixes, str):
            prefix = prefixes
        else:
            prefix = prefixes[0]

        self.ctx.message.content = f"{prefix}{fixed_content}"
        await self.ctx.bot.process_commands(self.ctx.message)

    @discord.ui.button(
        label="Help",
        emoji=discord.PartialEmoji(name="info", id=EMOJIS["info"]),
        style=discord.ButtonStyle.blurple,
    )
    async def get_help(self, itx: discord.Interaction, button: discord.ui.Button):
        instance: Help = self.ctx.bot.get_cog("Help")
        await self.ctx.invoke(instance.help, thing=self.command)


class GetHelpView(VanirView):
    def __init__(
        self,
        bot: Vanir,
        instance: VanirCog,
        command: commands.Command,
        user: discord.User,
    ):
        super().__init__(bot=bot)
        self.instance = instance
        self.command = command
        self.user = user

    @discord.ui.button(
        label="Get Help",
        style=discord.ButtonStyle.primary,
        emoji="\N{WHITE QUESTION MARK ORNAMENT}",
    )
    async def get_help(self, itx: discord.Interaction, button: discord.ui.Button):
        embed = await self.instance.command_details_embed(self.command, self.user)
        await itx.response.edit_message(embed=embed, view=None)


async def setup(bot: Vanir):
    await bot.add_cog(Errors(bot))
