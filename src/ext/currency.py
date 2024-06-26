from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from src.types.command import VanirCog, VanirModal, VanirView, vanir_group
from src.types.core import Vanir, VanirContext
from src.util.format import format_dict

if TYPE_CHECKING:
    from src.types.orm import Currency as DBCurrency


class Currency(VanirCog):
    """A custom currency system."""

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
    ) -> None:
        r"""Manage your coins [default: `+coins balance <user=you>`]."""
        await ctx.invoke(self.balance, user)

    @coins.command(aliases=["bal", "check", "wallet", "wal"])
    async def balance(
        self,
        ctx: VanirContext,
        user: discord.User = commands.param(
            description="Whose balance to view",
            default=lambda ctx: ctx.author,
            displayed_default="you",
        ),
    ) -> None:
        """Get yours, or someone else's balance'."""
        balance = await self.bot.db_currency.balance(user.id)

        embed = VanirContext.syn_embed(title=f"$**{balance:,}**", user=user)
        await ctx.reply(
            embed=embed,
            view=WalletOptionsView(bot=self.bot, user=ctx.author),
        )

    @coins.command(aliases=["send"])
    async def give(
        self,
        ctx: VanirContext,
        user: discord.User = commands.param(description="Who to send the funds to"),
        amount: commands.Range[int, 1] = commands.param(
            description="How many coins to send",
        ),
    ) -> None:
        """Give some coins to another user."""
        if amount < 0:
            msg = "Amount cannot be negative"
            raise ValueError(msg)
        from_bal = await self.bot.db_currency.balance(ctx.author.id)
        if from_bal < amount:
            msg = f"You only have $**{from_bal:,}**, you cannot send $**{amount:,}**"
            raise ValueError(
                msg,
            )

        to_bal = await self.bot.db_currency.balance(user.id)

        embed, view = await self.init_funds_transfer(
            from_user=ctx.author,
            to_user=user,
            amount=amount,
            from_bal=from_bal,
            to_bal=to_bal,
        )
        await ctx.reply(embed=embed, view=view)

    @coins.command(aliases=["ask", "req"])
    async def request(
        self,
        ctx: VanirContext,
        user: discord.User = commands.param(description="Who to request funds from"),
        amount: commands.Range[int, 1] = commands.param(
            description="How many coins to request",
        ),
    ) -> None:
        """Request coins from another user."""
        from_bal = await self.bot.db_currency.balance(user.id)
        if from_bal < amount:
            msg = f"{user.name} only has $**{from_bal:,}**, you cannot request $**{amount:,}"
            raise ValueError(
                msg,
            )

        to_bal = await self.bot.db_currency.balance(ctx.author.id)

        embed, view = await self.init_funds_transfer(
            from_user=user,
            to_user=ctx.author,
            amount=amount,
            from_bal=from_bal,
            to_bal=to_bal,
        )
        await ctx.reply(content=user.mention, embed=embed, view=view)

    async def init_funds_transfer(
        self,
        *,
        from_user: discord.User | discord.Member,
        to_user: discord.User | discord.Member,
        amount: int,
        from_bal: int,
        to_bal: int,
    ) -> tuple[discord.Embed, GiveCoinsView]:
        data = {
            "Amount": f"$**{amount:,}**",
            f"{from_user.name}": f"${from_bal:,} -> ${from_bal-amount:,}",  # from
            f"{to_user.name}": f"${to_bal:,} -> ${to_bal + amount:,}",  # to
        }

        embed = VanirContext.syn_embed(
            title=f"Transfer $**{amount:,}** to {to_user.name}?",
            description=f"This is **{(amount/from_bal * 100):.2f}**% of your total balance.\n{format_dict(data, linesplit=True, colons=False)}",
            user=from_user,
        )

        view = GiveCoinsView(
            self.bot,
            from_user,
            to_user,
            from_bal,
            to_bal,
            amount,
            db_instance=self.bot.db_currency,
        )

        return embed, view


class GiveCoinsView(VanirView):
    def __init__(
        self,
        bot: Vanir,
        from_user: discord.User | discord.Member,
        to_user: discord.User | discord.Member,
        from_bal: int,
        to_bal: int,
        amount: int,
        *,
        db_instance: DBCurrency,
    ) -> None:
        super().__init__(
            bot=bot,
            accept_itx=lambda itx: itx.user.id == from_user.id,
            user=from_user,
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
    async def send(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        new_from, new_to = await self.db_instance.transfer(
            self.from_user.id,
            self.to_user.id,
            self.amount,
        )

        data = {
            "Amount": f"$**{self.amount}**",
            f"{self.from_user.name}": f"${self.from_bal:,} -> ${new_from:,}",
            f"{self.to_user.name}": f"${self.to_bal:,} -> ${new_to:,}",
        }
        embed = VanirContext.syn_embed(
            title=f"Transferred $**{self.amount:,}** to {self.to_user.name}",
            description=format_dict(data, linesplit=True, colons=False),
            user=itx.user,
        )

        await itx.response.edit_message(embed=embed, view=None)

    @discord.ui.button(
        label="Cancel",
        emoji="\N{CROSS MARK}",
        style=discord.ButtonStyle.danger,
    )
    async def cancel(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        embed = VanirContext.syn_embed(
            title="Cancelled",
            description="Nothing has been transferred.",
            user=itx.user,
        )
        await itx.response.edit_message(embed=embed, view=None)


class WalletOptionsView(VanirView):
    @discord.ui.button(
        label="Send",
        emoji="\N{PACKAGE}",
        style=discord.ButtonStyle.primary,
    )
    async def send(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        await itx.response.send_modal(
            AmountPromptModal(
                bot=self.bot,
                from_user=itx.user,
                from_bal=await self.bot.db_currency.balance(itx.user.id),
                is_sending=True,
            ),
        )

    @discord.ui.button(
        label="Request",
        emoji="\N{ENVELOPE WITH DOWNWARDS ARROW ABOVE}",
        style=discord.ButtonStyle.success,
    )
    async def request(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await itx.response.send_modal(
            AmountPromptModal(
                bot=self.bot,
                from_user=itx.user,
                from_bal=await self.bot.db_currency.balance(itx.user.id),
                is_sending=False,
            ),
        )


class AmountPromptModal(VanirModal, title="Transfer"):
    def __init__(
        self,
        bot: Vanir,
        from_user: discord.User | discord.Member,
        from_bal: int,
        is_sending: bool,
    ) -> None:
        super().__init__(bot)
        self.from_user = from_user
        self.from_bal = from_bal
        self.is_sending = is_sending

    user_ident = discord.ui.TextInput(
        label="User",
        placeholder="Enter the user's name or ID",
    )
    amount = discord.ui.TextInput(
        label="Amount",
        placeholder="Enter the amount of coins",
    )

    async def on_submit(self, itx: discord.Interaction) -> None:
        user_ident = self.user_ident.value

        if not self.amount.value.isdigit():
            return await itx.response.send_message("Invalid amount", ephemeral=True)
        amount = int(self.amount.value)

        if amount < 0:
            return await itx.response.send_message(
                "Amount cannot be negative",
                ephemeral=True,
            )

        member: discord.Member | None = None

        if itx.guild is None:
            return await itx.response.send_message(
                "This command can only be used in a server",
                ephemeral=True,
            )

        if user_ident.isdigit():
            member = discord.utils.find(
                lambda user: user.name == user_ident or user.id == int(user_ident),
                itx.guild.members,
            )
        else:
            member = discord.utils.find(
                lambda user: user.name == user_ident,
                itx.guild.members,
            )

        if member is None:
            return await itx.response.send_message(
                f"No user with the name or ID {user_ident}",
                ephemeral=True,
            )

        if member.id == itx.user.id:
            return await itx.response.send_message(
                "You cannot mention yourself",
                ephemeral=True,
            )

        if self.is_sending:
            from_bal = self.from_bal
            to_bal = await self.bot.db_currency.balance(member.id)

            from_user = self.from_user
            to_user = member
        else:
            from_bal = await self.bot.db_currency.balance(member.id)
            to_bal = self.from_bal

            from_user = member
            to_user = self.from_user

        if from_bal < amount:
            return await itx.response.send_message(
                f"You only have $**{from_bal:,}**, you cannot send $**{amount:,}**",
                ephemeral=True,
            )

        cog: Currency = self.bot.get_cog("Currency")

        if cog is None:
            msg = "Currency cog not found"
            raise RuntimeError(msg)

        embed, view = await cog.init_funds_transfer(
            from_user=from_user,
            to_user=to_user,
            amount=amount,
            from_bal=from_bal,
            to_bal=to_bal,
        )
        await itx.response.edit_message(embed=embed, view=view)
        return None


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Currency(bot))
