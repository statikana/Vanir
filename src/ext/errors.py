import discord
from discord.ext import commands

from src.types.core import Vanir, VanirContext
from src.types.command import VanirCog, cog_hidden


@cog_hidden
class Errors(VanirCog):
    @commands.Cog.listener()
    async def on_command_error(self, ctx: VanirContext, error: commands.CommandError):
        if isinstance(error, commands.CommandInvokeError):
            print(f"Ignoring error in {ctx.command.qualified_name}: {error}")
            return

        embed = ctx.embed(
            title=f"Error - `{type(error).__name__}`: {error}",
            color=discord.Color.red(),
        )
        await ctx.reply(embed=embed, ephemeral=True)


async def setup(bot: Vanir):
    await bot.add_cog(Errors(bot))
