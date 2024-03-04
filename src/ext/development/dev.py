import discord
from discord.ext import commands

from src.types.command import (
    VanirCog,
)
from src.util.command import cog_hidden
from src.types.core import VanirContext


@cog_hidden
class Dev(VanirCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    @commands.group()
    @commands.is_owner()
    async def dev(self, ctx):
        """..."""
        pass

    @dev.command()
    @commands.is_owner()
    async def sync(self, ctx: VanirContext, *, guild_id: str | None = None):
        """Syncs commands to discord"""
        if guild_id:
            cmds = await self.bot.tree.sync(guild=discord.Object(id=int(guild_id)))
        else:
            cmds = await self.bot.tree.sync()

        await ctx.reply(
            embed=ctx.embed("Synced", description=",".join(c.name for c in cmds))
        )

    @dev.command()
    @commands.is_owner()
    async def desync(self, ctx: VanirContext):
        """Removes all commands, then syncs"""
        self.bot.recursively_remove_all_commands()
        await self.bot.tree.sync()
        await ctx.reply(str(ctx.bot.commands))

    @dev.command()
    @commands.is_owner()
    async def echo(self, ctx: VanirContext, *, message: str):
        """Replies"""
        await ctx.reply(message)

    @dev.command()
    @commands.is_owner()
    async def setbal(self, ctx: VanirContext, user: discord.User, amount: int):
        """Manually set user balance"""
        await self.bot.db_currency.set_balance(user.id, amount)
        await ctx.reply(f"{user.id} -> {amount}")


async def setup(bot):
    await bot.add_cog(Dev(bot))
