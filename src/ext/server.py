from src.types.command import VanirCog, AutoTablePager
from src.util.command import vanir_command
from src.types.core import VanirContext, Vanir


class Server(VanirCog):
    """Information about this server"""

    emoji = "\N{Hut}"

    @vanir_command()
    async def new(self, ctx: VanirContext):
        """Shows the list of all new members in the server"""
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)
        headers = ["name", "joined at"]
        dtypes = ["t", "t"]
        view = AutoTablePager(
            ctx.bot,
            ctx.author,
            headers=headers,
            rows=[[m.name, m.joined_at.strftime("%Y/%m/%d %H:%M:%S")] for m in members],
            dtypes=dtypes,
            rows_per_page=10,
        )
        embed = await view.update_embed()
        view.message = await ctx.reply(embed=embed, view=view)
        await view.update()


async def setup(bot: Vanir):
    await bot.add_cog(Server(bot))
