import discord
from discord import InteractionResponse
from discord.ext import commands

from src.types.command import VanirCog, cog_hidden, vanir_group, inherit, AutoCachedView, VanirView
from src.types.core import VanirContext
from src.types.util import MessageState


@cog_hidden
class Dev(VanirCog):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    @commands.group()
    @commands.is_owner()
    async def dev(self, ctx):
        pass

    @inherit
    @dev.command()
    async def sync(self, ctx: VanirContext, *, guild_id: str | None = None):
        if guild_id:
            await self.bot.tree.sync(guild=discord.Object(id=int(guild_id)))
        else:
            await self.bot.tree.sync()

        await ctx.reply(embed=ctx.embed("Synced"))

    @inherit
    @dev.command()
    async def echo(self, ctx: VanirContext, *, message: str):
        await ctx.reply(message)

    @inherit
    @dev.command()
    async def setbal(self, ctx: VanirContext, user: discord.User, amount: int):
        await self.bot.db_currency.set_balance(user.id, amount)
        await ctx.reply(f"{user.id} -> {amount}")

    @inherit
    @dev.command()
    async def vt(self, ctx: VanirContext):
        view = AutoCachedView(
            user=ctx.author
        )
        view.add_item(BasicSel())
        embed = ctx.embed(title="FIRST")
        await ctx.reply(embed=embed, view=view)


class BasicSel(discord.ui.Select[AutoCachedView]):
    def __init__(self):
        super().__init__(
            placeholder="choose",
            options=[discord.SelectOption(label=k) for k in ["grape", "raisin"]]
        )

    async def callback(self, itx: discord.Interaction):
        await self.view.collect(itx)
        print("post change", self.view.states)
        embed = VanirContext.syn_embed(
            title=self.values[0],
            author=itx.user
        )
        self.view.remove_item(self)
        await InteractionResponse(itx).edit_message(embed=embed, view=self.view)


async def setup(bot):
    await bot.add_cog(Dev(bot))
