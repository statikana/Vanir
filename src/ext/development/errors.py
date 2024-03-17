import discord
from discord.ext import commands

from src.types.command import VanirCog, VanirHybridCommand, VanirView
from src.types.core import Vanir, VanirContext
from src.util.command import cog_hidden
from src.util.parse import fuzzysearch


@cog_hidden
class Errors(VanirCog):
    @commands.Cog.listener()
    async def on_command_error(
        self, source: VanirContext | discord.Interaction, error: commands.CommandError
    ):
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
            list(cmd for cmd in commands if not cmd.hidden),
            key=lambda c: c.qualified_name,
            threshold=80,
        )
        if not results:
            return

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
        if isinstance(source, VanirContext):
            await source.reply(embed=embed, ephemeral=True)
        else:
            await source.response.send_message(embed=embed, ephemeral=True)


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
