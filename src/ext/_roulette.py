from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

import discord
import numpy as np

from src.types.command import (
    CloseButton,
    VanirModal,
    VanirView,
)

if TYPE_CHECKING:
    from src.types.core import VanirContext


async def roulette_embed(
    ctx: VanirContext,
) -> tuple[discord.Embed, discord.File, discord.File]:
    embed = ctx.embed(
        description="Place your bets! You can have up to 25 bets at once.",
    )
    image = discord.File("assets/roulette.png", filename="roulette.png")
    embed.set_image(url="attachment://roulette.png")
    embed.set_footer(text="You have 60 seconds to place your bets.")
    return embed, image


class RouletteView(VanirView):
    def __init__(
        self,
        ctx: VanirContext,
        initial_embed: discord.Embed,
        balance: int,
    ) -> None:
        super().__init__(ctx.bot, timeout=60, user=ctx.author)
        self.ctx = ctx
        self.selected_bets: list[SelectedBet] = []
        self.embed = initial_embed
        self.balance = balance

        self.add_item(BetSelector(ctx, embed=initial_embed, balance=balance))
        self.add_item(ConfirmButton(ctx))
        self.add_item(CloseButton())


class BetSelector(discord.ui.Select[RouletteView]):
    def __init__(
        self,
        ctx: VanirContext,
        embed: discord.Embed,
        balance: int,
    ) -> None:
        super().__init__(placeholder="Select a bet type...", min_values=1, max_values=1)
        self.ctx = ctx
        self.embed = embed
        self.balance = balance

        for bet in RouletteBetTypes:
            self.add_option(
                label=f"[{bet.value.payout:2}:1] {bet.value.name}",
                value=bet.name,
            )

    async def callback(self, itx: discord.Interaction) -> None:
        bet = RouletteBetTypes[self.values[0]].value
        if len(self.view.selected_bets) > 25:
            self.disabled = True
        modal = BetInputModal(
            self.ctx,
            self.view,
            bet=bet,
            embed=self.embed,
            balance=self.balance,
        )
        await itx.response.send_modal(modal)
        await modal.wait()

        selected_bet = SelectedBet(
            bet=bet,
            numbers=modal.calculated_numbers,
            wager=modal.wager,
        )
        self.view.selected_bets.append(selected_bet)

        # the itx from modal submit handes the GUI of the embed


class BetInputModal(VanirModal):
    def __init__(
        self,
        ctx: VanirContext,
        view: RouletteView,
        *,
        bet: RouletteBetType,
        embed: discord.Embed,
        balance: int,
    ) -> None:
        super().__init__(ctx.bot, title=f"{bet.name} bet")
        self.bet = bet
        self.view = view
        self.ctx = ctx
        self.embed = embed
        self.balance = balance

        self.calculated_numbers: list[int] = discord.utils.MISSING

        if sum(check.n_args for check in bet.input_checks) != len(bet.input_names):
            msg = "dev fucked up: The sum of n_args of all checks must be equal to the number of inputs required."
            raise RuntimeError(msg)

        for name in bet.input_names:
            self.add_item(
                discord.ui.TextInput(label=name, style=discord.TextStyle.short),
            )

        self.add_item(
            discord.ui.TextInput(
                label=f"Wager [You Have: ${self.balance:,}]",
                placeholder="How much would you like to wager on this bet?",
            ),
        )

    async def on_submit(self, itx: discord.Interaction) -> None:
        *inputs, wager = (
            item.value
            for item in self.children
            if isinstance(item, discord.ui.TextInput)
        )

        if not wager.isdigit():
            msg = "Wager must be a number"
            raise ValueError(msg)
        wager = int(wager)
        self.wager = wager

        function_input: tuple[int]

        def intcheck(*values: str):
            for v in values:
                if not v.isdigit():
                    raise ValueError
                yield int(v)

        if self.bet.input_requirement is InputRequirementType.Color:
            color = inputs[0]
            if (color := color.lower()) not in ("red", "black"):
                msg = f"Invalid color: {color}"
                raise ValueError(msg)
            function_input = [0 if color == "black" else 1]

        elif self.bet.input_requirement is InputRequirementType.OddOrEven:
            odd_or_even = inputs[0]
            if (odd_or_even := odd_or_even.lower()) not in ("odd", "even"):
                msg = f"Invalid odd or even: {odd_or_even}"
                raise ValueError(msg)
            function_input = [0 if odd_or_even == "even" else 1]

        elif self.bet.input_requirement is InputRequirementType.HighOrLow:
            high_or_low = inputs[0]
            if (high_or_low := high_or_low.lower()) not in ("high", "low"):
                msg = f"Invalid high or low: {high_or_low}"
                raise ValueError(msg)
            function_input = [0 if high_or_low == "low" else 1]

        elif self.bet.input_requirement in (
            InputRequirementType.Single,
            InputRequirementType.Double,
            InputRequirementType.Triple,
            InputRequirementType.Column,
        ):
            function_input = tuple(intcheck(*inputs))

        else:
            msg = "oops"
            raise RuntimeError(msg)

        for flag in self.bet.flags:
            function_input = flag(*function_input)

        checking_index: int = 0
        for check in self.bet.input_checks:
            args = function_input[checking_index : checking_index + check.n_args]
            check.check(args)  # will raise an error if the check fails
            checking_index += check.n_args

        self.calculated_numbers = self.bet.number_function(*function_input)
        self.embed.add_field(
            name=f"`[{self.bet.payout:>2}:1]` {self.bet.name}",
            value=f"Chose: `{", ".join(inputs)}`\n[`{len(self.calculated_numbers)}` Number Bet]\nWager: $**{wager:,}**",
        )
        await itx.response.edit_message(embed=self.embed, view=self.view)


class ConfirmButton(discord.ui.Button[RouletteView]):
    def __init__(self, ctx: VanirContext) -> None:
        super().__init__(label="Confirm", style=discord.ButtonStyle.success)
        self.ctx = ctx

    async def callback(self, itx: discord.Interaction) -> None:
        bets = self.view.selected_bets

        number = np.random.choice(wheel)  # noqa: NPY002 # ??

        total_winnings = 0

        for bet in bets:
            if number in bet.numbers:
                total_winnings += bet.bet.payout * bet.wager
            else:
                total_winnings -= bet.wager

        balance = await self.ctx.bot.db_currency.add(self.ctx.author.id, total_winnings)

        embed = self.ctx.embed(
            title=f"Roulette Results - Spun: **{number}**",
            description=f"You {"won" if total_winnings > 0 else "lost" if total_winnings < 0 else "broke even at"} $**{abs(total_winnings):,}**",
        )
        embed.add_field(
            name="Current Balance",
            value=f"$**{balance:,}**",
        )
        embed.add_field(
            name="Change",
            value=f"{"+" if total_winnings >= 0 else ""}{balance/(balance-total_winnings)-1:.2%}",
        )
        # add fields for new user balance and total winnings
        # option for new game, with total_winnings as the wager
        # option for new game, with custom amount as the wager
        await itx.response.edit_message(
            embeds=[*itx.message.embeds, embed],
            view=None,
            attachments=[],
        )


table = np.array(
    [
        [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
        [0, 2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
        [0, 1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
    ],
)


wheel = np.array(
    [
        0,
        32,
        15,
        19,
        4,
        21,
        2,
        25,
        17,
        34,
        6,
        27,
        13,
        36,
        11,
        30,
        8,
        23,
        10,
        5,
        24,
        16,
        33,
        1,
        20,
        14,
        31,
        9,
        22,
        18,
        29,
        7,
        28,
        12,
        35,
        3,
        26,
    ],
)


# 0 is black, 1 is red, 2 is green
colors = np.array(
    [
        [2, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1],
        [2, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0],
        [2, 1, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 1],
    ],
)


class InputRequirementType(Enum):
    Single = 1
    Double = 2
    Triple = 3
    Color = 4
    OddOrEven = 5
    HighOrLow = 6
    Column = 7


@dataclass(kw_only=True)
class RouletteBetType:
    name: str
    "The name of the bet type"
    group: RouletteBetTypeGroup
    "The group of the bet type"
    number_function: Callable[[tuple[int, ...]], list[int]] = lambda x: x  # noqa: E731
    """A function that takes a list of table indicies and returns the indicies that the bet type
    applies to - ie for a split bet, it would return the index and the index + 1 or -1, depending
    on the position of the index on the table."""
    payout: int
    """The payout for the bet type, ie payout: 35 means that the player will receive 35 times their bet"""
    input_requirement: InputRequirementType
    """The input requirement for the bet type, ie Single means that the player must input a single number"""
    input_names: list[str]
    """The name of the input, ie for a single bet, it would be "The number you want to bet on" """
    input_checks: list[RouletteCheck] = field(
        default_factory=list,
    )
    """A list of checks that the input must pass in order to be valid. Sum of n_args of all checks must be equal to the number of inputs required."""
    flags: list[BetFlag] = field(
        default_factory=list,
    )
    """A list of flags that will be applied to the input before it is passed to the number_function"""


class BetFlag(Enum):
    ZeroIndexed = lambda *v: tuple(n - 1 for n in v)  # noqa: E731
    """The bet type is zero indexed, meaning that the input should be 0-36, not 1-37"""


class RouletteBetTypeGroup(Enum):
    Inside = "Inside"
    Outside = "Outside"
    FixedCalled = "Fixed Called"
    VariableCalled = "Variable Called"


@dataclass
class SelectedBet:
    bet: RouletteBetType
    numbers: list[int]
    wager: int


class RouletteCheck:
    def __init__(
        self,
        n_args: int,
        expr: Callable[[tuple[int, ...]], bool],
        error: RouletteError,
    ) -> None:
        self.n_args = n_args
        self.expr = expr
        self.error = error

    def check(self, args: tuple[int]) -> bool:
        if len(args) != self.n_args:
            msg = "Invalid number of arguments passed to check function."
            raise RuntimeError(msg)
        if not (result := self.expr(*args)):
            raise self.error
        return result


class RouletteError(Exception):
    pass


class InvalidShapeError(RouletteError):
    """
    The shape of the input was invalid - ie, the four numbers to a
    corner bet were not in the shape of a square on the table.
    """


class OutOfBoundsError(RouletteError):
    """The number was too large or small for the kind of bet you were trying to make."""


class RouletteChecks:
    def straight_up(self: int) -> bool:
        return 0 <= self < 37

    def split(self: int, n2: int) -> bool:
        return abs(self - n2) in (1, 3)

    def street(self: int) -> bool:
        return 0 <= self < 12

    def corner(self: int, n2: int, n3: int, n4: int) -> bool:
        self, n2, n3, n4 = sorted([self, n2, n3, n4])
        return all(
            (
                self + 1 == n2,
                self + 3 == n3,
                n3 + 1 == n4,
                n2 + 3 == n4,
            ),
        )

    def dozen(self: int) -> bool:
        return 0 <= self <= 2


class RouletteBetTypes(Enum):
    StraightUp = RouletteBetType(
        name="Straight Up",
        group=RouletteBetTypeGroup.Inside,
        number_function=lambda n: [n],
        payout=35,
        input_requirement=InputRequirementType.Single,
        input_names=["The number you want to bet on [0-36]"],
        input_checks=[
            RouletteCheck(1, RouletteChecks.straight_up, OutOfBoundsError),
        ],
    )
    Split = RouletteBetType(
        name="Split",
        group=RouletteBetTypeGroup.Inside,
        number_function=lambda n1, n2: [n1, n2],
        payout=17,
        input_requirement=InputRequirementType.Double,
        input_names=[
            "The first number you want to bet on [0-36]",
            "Second number - adjacent to the first [0-36]",
        ],
        input_checks=[
            RouletteCheck(2, RouletteChecks.split, InvalidShapeError),
        ],
        flags=[],
    )
    Street = RouletteBetType(
        name="Street / Row",
        group=RouletteBetTypeGroup.Inside,
        number_function=lambda n: [n * 3, n * 3 + 1, n * 3 + 2],
        payout=11,
        input_requirement=InputRequirementType.Single,
        input_names=[
            "The row to bet on [1-12]",
        ],
        input_checks=[
            RouletteCheck(1, RouletteChecks.street, OutOfBoundsError),
        ],
        flags=[BetFlag.ZeroIndexed],
    )
    Corner = RouletteBetType(
        name="Corner",
        group=RouletteBetTypeGroup.Inside,
        number_function=lambda n1, n2, n3, n4: [n1, n2, n3, n4],
        payout=8,
        input_requirement=InputRequirementType.Single,
        input_names=[
            "The first number of the square",
            "The second number of the square",
            "The third number of the square",
            "The fourth number of the square",
        ],
        input_checks=[
            RouletteCheck(4, RouletteChecks.corner, InvalidShapeError),
        ],
        flags=[],
    )
    SixLine = RouletteBetType(
        name="Six Line",
        group=RouletteBetTypeGroup.Inside,
        number_function=lambda r1, r2: np.append(table[r1], table[r2]),
        payout=5,
        input_requirement=InputRequirementType.Double,
        input_names=[
            "The first row to bet on",
            "The second row to bet on",
        ],
        input_checks=[
            RouletteCheck(1, RouletteChecks.street, OutOfBoundsError),
            RouletteCheck(1, RouletteChecks.street, OutOfBoundsError),
        ],
        flags=[BetFlag.ZeroIndexed],
    )

    RedOrBlack = RouletteBetType(
        name="Red or Black",
        group=RouletteBetTypeGroup.Outside,
        number_function=lambda color: table[colors == color],
        payout=1,
        input_requirement=InputRequirementType.Color,
        input_names=["The color you want to bet on"],
        input_checks=[
            RouletteCheck(1, lambda *_: True, RouletteError),
        ],
        flags=[],
    )

    OddOrEven = RouletteBetType(
        name="Odd or Even",
        group=RouletteBetTypeGroup.Outside,
        number_function=lambda is_even: table[
            table % 2 == int(is_even)
        ],  # 0 for even, 1 for odd
        payout=1,
        input_requirement=InputRequirementType.OddOrEven,
        input_names=["Odd or Even"],
        input_checks=[
            RouletteCheck(1, lambda *_: True, RouletteError),
        ],
    )
    HighOrLow = RouletteBetType(
        name="High or Low",
        group=RouletteBetTypeGroup.Outside,
        number_function=lambda is_high: table[
            table > 18 if bool(is_high) else table <= 18
        ],
        payout=1,
        input_requirement=InputRequirementType.HighOrLow,
        input_names=["High or Low"],
        input_checks=[
            RouletteCheck(1, lambda *_: True, RouletteError),
        ],
    )
    Dozens = RouletteBetType(
        name="Dozens",
        group=RouletteBetTypeGroup.Outside,
        number_function=lambda n: table[:, n * 4 + 1 : (n + 1) * 4 + 1].flatten(),
        payout=2,
        input_requirement=InputRequirementType.Single,
        input_names=["The dozen [1: 1-12, 2: 13-24, 3: 25-36]"],
        input_checks=[
            RouletteCheck(1, RouletteChecks.dozen, OutOfBoundsError),
        ],
        flags=[BetFlag.ZeroIndexed],
    )
