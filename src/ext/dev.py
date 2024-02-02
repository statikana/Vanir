import discord
from discord.ext import commands

from src.types.command_types import VanirCog, cog_hidden
from src.types.core_types import Vanir, VanirContext


@cog_hidden
class Dev(VanirCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    @commands.group()
    async def dev(self, ctx):
        pass

    @dev.command(cls=VanirCommand)
    @commands.is_owner()
    async def sync(self, ctx: VanirContext, *, guild_id: str):
        if guild_id:
            await self.vanir.tree.sync(guild=discord.Object(id=int(guild_id)))
        else:
            await self.vanir.tree.sync()

        await ctx.send(embed=ctx.embed("Synced"))
