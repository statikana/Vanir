import discord
from enum import Enum

from discord.ext import commands

from src.types.command import VanirCog, VanirPager, vanir_command
from src.types.core import VanirContext, Vanir


class TypeThing(Enum):
    A = 15
    B = "ok"


class Server(VanirCog):
    @vanir_command()
    async def new(self, ctx: VanirContext):
        """Shows the list of all new members in the server"""
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)
        paginator = ServerPager(ctx.author, members, 10)
        embed = await paginator.update_embed()
        paginator.message = await ctx.reply(embed=embed, view=paginator)
        await paginator.update()

    @commands.command()
    async def log(self, ctx: VanirContext, type_filter: TypeThing = None):
        await ctx.reply(f"{type_filter}")


class ServerPager(VanirPager[discord.Member]):
    async def update_embed(self) -> discord.Embed:
        members = self.items[
            self.page * self.items_per_page : (self.page + 1) * self.items_per_page
        ]
        embed = VanirContext.syn_embed(title="New Members", author=self.user)
        display = []
        for m in members:
            just = 25
            n_spaces = max(0, just - len(m.display_name)) - 3
            char = "\\_"
            fmt = f"{m.mention}{char*n_spaces}{discord.utils.format_dt(m.joined_at, 'R')} [ID `{m.id}]`"
            display.append(fmt)
        embed.description = "\n".join(display)
        return embed


async def setup(bot: Vanir):
    await bot.add_cog(Server(bot))