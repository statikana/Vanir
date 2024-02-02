import enum
import logging
import math
from typing import TypeVar, Generic, Callable, Any

import discord
from discord import Interaction
from discord.ext import commands
from discord.ext.commands import Command, Cog

from src.types.core_types import Vanir

VanirPagerT = TypeVar("VanirPagerT")
CommandT = TypeVar("CommandT", bound=commands.Command)


class AcceptItx(enum.Enum):
    ANY = 0
    AUTHOR_ONLY = 1
    NOT_AUTHOR = 2


class VanirCog(commands.Cog):
    def __init__(self, bot: Vanir):
        self.vanir = bot
        self.hidden: bool = False  # gets set to true if the class is decorated by @hidden


class VanirView(discord.ui.View):
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


class VanirPager(VanirView, Generic[VanirPagerT]):
    def __init__(
            self, items: list[VanirPagerT], items_per_page: int, *, start_page: int = 0
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
            VanirPager.disable(self.first, self.back)
        else:
            VanirPager.enable(self.first, self.back)

        if self.page == self.n_pages - 1:
            VanirPager.disable(self.next, self.last)
        else:
            VanirPager.enable(self.next, self.last)

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
                f"Pager has no message attached (VanirPagerT: {VanirPagerT}), cannot update message"
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


def add_extras(**extras) -> Callable[[CommandT], CommandT]:
    def decorator(cmd: CommandT) -> CommandT:
        cmd.extras = extras
        return cmd

    return decorator


def _deco_factory(ctype: type[CommandT], name: str | None = None, **extras) -> Callable[[Any], CommandT]:
    def decorator(func) -> CommandT:
        partial = ctype(func, name=name)
        cmd = add_extras(**extras)(partial)

        if isinstance(cmd, commands.Group):

            def fix_subcommanding(cmd_name: str | None = None):
                # this will have the same `extras` as the parent command
                parent: commands.Group = cmd

                def decorator_inner(sub_func) -> CommandT:
                    # create a regular command, then apply the parent's extras to it
                    basic_cmd = parent.command(name=name)(sub_func)
                    return add_extras(**parent.extras)(basic_cmd)

            cmd.command = fix_subcommanding

        return cmd

    return decorator


def vanir_command(name: str | None = None, *, hidden: bool = False) -> Callable[[Any], commands.Command]:
    return _deco_factory(commands.Command, name, hidden=hidden)


def vanir_hybrid_command(name: str | None = None, *, hidden: bool = False) -> Callable[[Any], commands.HybridCommand]:
    return _deco_factory(commands.HybridCommand, name, hidden=hidden)


def vanir_group(name: str | None = None, *, hidden: bool = False) -> Callable[[Any], commands.Group]:
    return _deco_factory(commands.Group, name, hidden=hidden)


def vanir_hybrid_group(name: str | None = None, *, hidden: bool = False) -> Callable[[Any], commands.HybridGroup]:
    return _deco_factory(commands.HybridGroup, name, hidden=hidden)


def cog_hidden(cls: type[VanirCog]):
    """A wrapper which sets the `VanirCog().hidden` flag to True when this class initializes"""

    def cls_init(self: VanirCog, bot: Vanir):
        """Overwrites the cog's init"""
        super().__init__(bot)
        self.__init__(bot)  # call any code which is already here
        self.hidden = True

    cls.__init__ = cls_init
    return cls
