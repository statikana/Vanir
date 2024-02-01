import enum
import logging
import math
from typing import TypeVar, Generic

import discord
from discord import Interaction
from discord.ext import commands

from src.types.charm_types import Charm

CharmPagerT = TypeVar("CharmPagerT")


class AcceptItx(enum.Enum):
    ANY = 0
    AUTHOR_ONLY = 1
    NOT_AUTHOR = 2


class CharmCog(commands.Cog):
    def __init__(self, charm: Charm):
        self.charm = charm


class CharmView(discord.ui.View):
    def __init__(self, *, accept_itx: AcceptItx, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.accept_itx = accept_itx
        self.author: discord.User | None = None

    async def interaction_check(self, itx: Interaction, /) -> bool:
        if self.accept_itx == AcceptItx.AUTHOR_ONLY:
            return itx.user.id == self.author.id
        if self.accept_itx == AcceptItx.ANY:
            return True
        if self.accept_itx == AcceptItx.NOT_AUTHOR:
            return itx.user.id != self.author.id


class CharmPager(CharmView, Generic[CharmPagerT]):
    def __init__(
        self, items: list[CharmPagerT], items_per_page: int, *, start_page: int = 0
    ):
        super().__init__(accept_itx=AcceptItx.AUTHOR_ONLY)
        self.items = items
        self.items_per_page = items_per_page

        self.page = start_page
        if items_per_page <= 0:
            raise ValueError("items_per_page must be greater than 0")
        if len(items) <= 0:
            raise ValueError("items must not be empty")
        self.n_pages = math.ceil(len(items) / items_per_page)

        self.message: discord.Message | None = None

    @discord.ui.button(emoji="\N{Black Left-Pointing Double Triangle}")
    async def first(self, _itx: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await self.update(button)

    @discord.ui.button(emoji="\N{Leftwards Black Arrow}")
    async def back(self, _itx: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.update(button)

    @discord.ui.button(emoji="\N{Cross Mark}")
    async def close(self, _itx: discord.Interaction, button: discord.ui.Button):
        for item in self.items:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

        await self.update(button)

    @discord.ui.button(emoji="\N{Rightwards Black Arrow}")
    async def next(self, _itx: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.update(button)

    @discord.ui.button(emoji="\N{Black Right-Pointing Double Triangle}")
    async def last(self, _itx: discord.Interaction, button: discord.ui.Button):
        self.page = self.n_pages - 1
        await self.update(button)

    async def update(self, source_button: discord.ui.Button):
        """Called after every button press - enables and disables the appropriate buttons, and changes colors.
        Also fetches te new embed and edits the message and view to the new content."""
        if self.page == 0:
            CharmPager.disable(self.first, self.back)
        else:
            CharmPager.enable(self.first, self.back)

        if self.page == self.n_pages - 1:
            CharmPager.disable(self.next, self.last)
        else:
            CharmPager.enable(self.next, self.last)

        for i in self.children:
            if isinstance(i, discord.ui.Button):
                if i == source_button:
                    i.style = discord.ButtonStyle.success
                else:
                    i.style = discord.ButtonStyle.grey

        if self.message is not None:
            embed = await self.update_embed()
            await self.message.edit(embed=embed, view=self)
        else:
            logging.warning(
                f"Pager has no message attached (CharmPagerT: {CharmPagerT}), cannot update message"
            )

    async def update_embed(self) -> discord.Embed:
        """To be implemented by children classes"""
        raise NotImplemented

    @staticmethod
    def enable(*buttons: discord.ui.Button):
        for button in buttons:
            button.disabled = False

    @staticmethod
    def disable(*buttons: discord.ui.Button):
        for button in buttons:
            button.disabled = True
