from src.ext._roulette import RouletteView, roulette_embed
from src.types.command import VanirCog, vanir_command
from src.types.core import Vanir, VanirContext


class Casino(VanirCog):
    """Real life simulator lmao."""

    emoji = "\N{GAME DIE}"

    @vanir_command(aliases=["rl"])
    async def roulette(
        self,
        ctx: VanirContext,
    ) -> None:
        """Play a game roulette."""
        embed, image = await roulette_embed(ctx)
        balance = await ctx.bot.db_currency.balance(ctx.author.id)

        view = RouletteView(ctx, embed, balance)
        await ctx.send(embed=embed, view=view, file=image)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Casino(bot))
