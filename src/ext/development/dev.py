import asyncio
import os

import discord
from discord.ext import commands

from src.types.command import (
    VanirCog,
)
from src.types.core import VanirContext
from src.util.command import cog_hidden



@cog_hidden
class Dev(VanirCog):
    @commands.group()
    @commands.is_owner()
    async def dev(self, ctx):
        """..."""
        pass

    @dev.command()
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
    async def desync(self, ctx: VanirContext):
        """Removes all commands, then syncs"""
        self.bot.recursively_remove_all_commands()
        await self.bot.tree.sync()
        await ctx.reply(str(ctx.bot.commands))

    @dev.command()
    async def echo(self, ctx: VanirContext, *, message: str):
        """Replies"""
        await ctx.reply(message)

    @dev.command()
    async def setbal(self, ctx: VanirContext, user: discord.User, amount: int):
        """Manually set user balance"""
        await self.bot.db_currency.set_balance(user.id, amount)
        await ctx.reply(f"{user.id} -> {amount}")

    @dev.command()
    async def sql(self, ctx: VanirContext, *, query: str):
        """Run a SQL query"""
        async with self.bot.pool.acquire() as conn:
            result = await conn.fetch(query)
            await ctx.reply(str(result))

    @dev.command(aliases=["dbg"])
    async def debug(self, ctx: VanirContext, val: bool | None = None):
        """Toggle debug mode"""
        if val is not None:
            self.bot.debug = val
        await ctx.reply(f"Debug mode is {self.bot.debug}")

    @dev.command()
    async def error(self, ctx: VanirContext):
        """Throw an error"""
        raise ValueError("This is a test error")


async def setup(bot):
    await bot.add_cog(Dev(bot))
