import discord
from discord.ext import commands

from src.types.core import Vanir, VanirContext
from src.types.command import VanirCog
from src.util.command import cog_hidden


@cog_hidden
class Errors(VanirCog):
    @commands.Cog.listener()
    async def on_command_error(
        self, source: VanirContext | discord.Interaction, error: commands.CommandError
    ):
        if isinstance(error, commands.CommandNotFound):
            return await self.on_command_not_found(source, error)

        title = f"Error - `{type(error).__name__}`: {error}"
        color = discord.Color.red()

        if isinstance(source, VanirContext):
            embed = VanirContext.syn_embed(title=title, color=color, user=source.author)
            await source.reply(embed=embed)
        else:
            embed = VanirContext.syn_embed(title=title, color=color, user=source.user)
            await source.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: Vanir):
    await bot.add_cog(Errors(bot))
