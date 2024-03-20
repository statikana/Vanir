import discord
from discord.ext import commands

from src.types.command import (
    AcceptItx,
    CloseButton,
    VanirCog,
    VanirHybridCommand,
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
        if self.bot.debug:
            raise error
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

        def alias_string(cmd: VanirHybridCommand):
            if cmd.aliases:
                return f"[{', '.join(f'`{a}`' for a in cmd.aliases)}]"
            return ""

        recommended = "\n".join(
            f"• `\{cmd.qualified_name}` {alias_string(cmd)}\n➥*{cmd.short_doc}*"
            for cmd in results[:5]
        )
        embed = VanirContext.syn_embed(
            title="Command not found",
            description=f"Did you mean...\n{recommended}",
            user=user,
            color=discord.Color.red(),
        )
        if isinstance(source, discord.Interaction):
            try:
                source = VanirContext.from_interaction(source)
            except ValueError:
                pass

        if isinstance(source, VanirContext):
            view = CommandNotFoundHelper(source, results[:25])
        else:
            view = None

        await source.reply(embed=embed, view=view, ephemeral=True)


class CommandNotFoundHelper(VanirView):
    def __init__(self, ctx: VanirContext, commands: list[commands.Command]):
        super().__init__(bot=ctx.bot, user=ctx.author)
        self.ctx = ctx
        self.commands = commands

        self.add_item(RerouteCommandSelect(ctx, commands))
        self.add_item(CloseButton())


class RerouteCommandSelect(discord.ui.Select):
    def __init__(self, ctx: VanirContext, commands: list[commands.Command]):
        options = [
            discord.SelectOption(
                label=cmd.qualified_name,
                description=cmd.short_doc,
                value=cmd.qualified_name,
            )
            for cmd in commands
        ]
        super().__init__(options=options, placeholder="Did you mean...", max_values=1)
        self.ctx = ctx

    async def callback(self, itx: discord.Interaction):
        await itx.message.delete()
        previous = self.ctx.message.content.split()
        new = self.values[0].split()
        previous[: len(new)] = new
        fixed_content = " ".join(previous)
        prefixes = await self.ctx.bot.get_prefix(self.ctx.message)

        if isinstance(prefixes, str):
            prefix = prefixes
        else:
            prefix = prefixes[0]

        self.ctx.message.content = f"{prefix}{fixed_content}"
        await self.ctx.bot.process_commands(self.ctx.message)


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
