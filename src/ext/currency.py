import discord
from discord.ext import commands

from src.types.command import VanirCog, VanirView, vanir_group
from src.types.core import Vanir, VanirContext
from src.types.database import Currency as DBCurrency
from src.util.fmt import fmt_dict


class Currency(VanirCog):
    """A custom currency system"""

    emoji = "\N{COIN}"

    @vanir_group(aliases=["currency", "cur"])
    async def coins(
        self,
        ctx: VanirContext,
        user: discord.User = commands.param(
            description="Whose balance to view",
            default=lambda ctx: ctx.author,
            displayed_default="you",
        ),
    ):
        await ctx.invoke(self.balance, user)  # type: ignore

    @coins.command(aliases=["bal", "check"])
    async def balance(
        self,
        ctx: VanirContext,
        user: discord.User = commands.param(
            description="Whose balance to view",
            default=lambda ctx: ctx.author,
            displayed_default="you",
        ),
    ):
        """Get yours, or someone else's balance'"""
        balance = await self.bot.db_currency.balance(user.id)

        embed = VanirContext.syn_embed(title=f"{balance:,}\N{COIN}", user=user)
        await ctx.reply(embed=embed)

    @coins.command(aliases=["send"])
    async def give(
        self,
        ctx: VanirContext,
        user: discord.User = commands.param(description="Who to send the funds to"),
        amount: commands.Range[int, 1] = commands.param(
            description="How many coins to send"
        ),
    ):
        """Give some coins to another user"""
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        from_bal = await self.bot.db_currency.balance(ctx.author.id)
        if from_bal < amount:
            raise ValueError(
                f"You only have {from_bal:,}\N{COIN}, you cannot send {amount:,}\N{COIN}"
            )

        to_bal = await self.bot.db_currency.balance(user.id)

        data = {
            "Amount": f"`{amount}`\N{COIN}",
            f"{ctx.author.name} [ID {ctx.author.id}]": f"{from_bal:,}\N{COIN} -> {from_bal-amount:,}\N{COIN}",  # from
            f"{user.name} [ID {user.id}]": f"{to_bal:,}\N{COIN} -> {to_bal + amount:,}\N{COIN}",  # to
        }

        embed = ctx.embed(
            title=f"Transfer {amount:,}\N{COIN} to {user.name}?",
            description=f"This is **{(amount/from_bal * 100):.2f}**% of your total balance.\nTransfer info:\n{fmt_dict(data, linesplit=True)}",
        )

        view = GiveCoinsView(
            ctx.bot,
            ctx.author,
            user,
            from_bal,
            to_bal,
            amount,
            db_instance=self.bot.db_currency,
        )

        await ctx.reply(embed=embed, view=view)

    @coins.command(aliases=["ask", "req"])
    async def request(
        self,
        ctx: VanirContext,
        user: discord.User = commands.param(description="Who to request funds from"),
        amount: commands.Range[int, 1] = commands.param(
            description="How many coins to request"
        ),
    ):
        """Request coins from another user"""
        from_bal = await self.bot.db_currency.balance(user.id)
        if from_bal < amount:
            raise ValueError(
                f"{user.name} only has {from_bal:,}\N{COIN}, you cannot request {amount:,}\N{COIN}"
            )

        to_bal = await self.bot.db_currency.balance(ctx.author.id)

        data = {
            "Amount": f"`{amount}`\N{COIN}",
            f"{user.name} [ID {user.id}]": f"{from_bal:,} -> {from_bal-amount:,}\N{COIN}",  # from
            f"{ctx.author.name} [ID {ctx.author.id}]": f"{to_bal:,} -> {to_bal + amount:,}\N{COIN}",  # to
        }

        embed = ctx.embed(
            title=f"Transfer {amount:,}\N{COIN} to {ctx.author}?",
            description=f"This is **{(amount/from_bal * 100):.2f}**% of your total balance.\nTransfer info:\n{fmt_dict(data, linesplit=True)}",
        )

        view = GiveCoinsView(
            ctx.bot,
            user,
            ctx.author,
            from_bal,
            to_bal,
            amount,
            db_instance=self.bot.db_currency,
        )

        await ctx.reply(content=user.mention, embed=embed, view=view)


class GiveCoinsView(VanirView):
    def __init__(
        self,
        bot: Vanir,
        from_user: discord.User,
        to_user: discord.User,
        from_bal: int,
        to_bal: int,
        amount: int,
        *,
        db_instance: DBCurrency,
    ) -> None:
        super().__init__(
            bot=bot, accept_itx=lambda itx: itx.user.id == from_user.id, user=from_user
        )
        self.from_user = from_user
        self.to_user = to_user
        self.from_bal = from_bal
        self.to_bal = to_bal
        self.amount = amount
        self.db_instance = db_instance

    @discord.ui.button(
        label="Send",
        emoji="\N{WHITE HEAVY CHECK MARK}",
        style=discord.ButtonStyle.success,
    )
    async def send(self, itx: discord.Interaction, button: discord.ui.Button):
        new_from, new_to = await self.db_instance.transfer(
            self.from_user.id, self.to_user.id, self.amount
        )

        data = {
            "Amount": f"`{self.amount}`\N{COIN}",
            f"{self.from_user.name} [ID {self.from_user.id}]": f"{self.from_bal:,}\N{COIN} -> {new_from:,}\N{COIN}",
            f"{self.to_user.name} [ID {self.to_user.id}": f"{self.to_bal:,}\N{COIN} -> {new_to:,}\N{COIN}",
        }
        embed = VanirContext.syn_embed(
            title=f"Transferred {self.amount:,}\N{COIN} to {self.to_user.name}",
            description=fmt_dict(data, linesplit=True),
            user=itx.user,
        )

        await itx.response.edit_message(embed=embed, view=None)

    @discord.ui.button(
        label="Cancel", emoji="\N{CROSS MARK}", style=discord.ButtonStyle.danger
    )
    async def cancel(self, itx: discord.Interaction, button: discord.ui.Button):
        embed = VanirContext.syn_embed(
            title="Cancelled",
            description="Nothing has been transferred.",
            user=itx.user,
        )
        await itx.response.edit_message(embed=embed, view=None)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Currency(bot))
