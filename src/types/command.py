import enum
import functools
import inspect
import logging
import math
from typing import TypeVar, Generic, Callable, Any, Coroutine, Awaitable
from asyncio import iscoroutinefunction

import discord
from discord import Interaction, InteractionResponse
from discord.ext import commands

from src.types.core import Vanir
from src.types.util import MessageStateCache

empty = inspect.Parameter.empty

VanirPagerT = TypeVar("VanirPagerT")
CommandT = TypeVar("CommandT", bound=commands.Command)


class AcceptItx(enum.Enum):
    ANY = 0
    AUTHOR_ONLY = 1
    NOT_AUTHOR = 2


class VanirCog(commands.Cog):
    def __init__(self, bot: Vanir):
        self.bot = bot
        self.hidden: bool = (
            False  # gets set to true if the class is decorated by @hidden
        )


class VanirView(discord.ui.View):
    def __init__(
        self,
        *,
        user: discord.User | None = None,
        state_cache: MessageStateCache = MessageStateCache(),
        accept_itx: (
            AcceptItx | Callable[[discord.Interaction], bool | Awaitable[bool]]
        ) = AcceptItx.AUTHOR_ONLY,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.accept_itx = accept_itx
        self.user = user
        self.state_cache = state_cache

    async def interaction_check(self, itx: Interaction, /) -> bool:
        async def inner():
            if isinstance(self.accept_itx, AcceptItx):
                if self.accept_itx == AcceptItx.ANY:
                    return True
                if self.user is None:
                    raise ValueError(
                        "If view does not accept every interaction and uses AcceptItx, .user must be set."
                    )
                if self.accept_itx == AcceptItx.AUTHOR_ONLY:
                    return itx.user.id == self.user.id
                if self.accept_itx == AcceptItx.NOT_AUTHOR:
                    return itx.user.id != self.user.id
                return False
            else:
                if iscoroutinefunction(self.accept_itx):
                    return await self.accept_itx(itx)
                return self.accept_itx(itx)

        result = await inner()
        if result is False:
            try:
                await itx.response.send_message(
                    "You can't interact with this", ephemeral=True
                )
            except discord.InteractionResponded:
                await itx.followup.send("You can't interact with this", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="\N{Black Left-Pointing Triangle}", disabled=True)
    async def previous_state(self, itx: discord.Interaction, button: discord.ui.Button):

        # the way the `.response` property is defined on discord.Interaction messes with my linter
        # this is the same thing, kind of
        # (it still doesn't work if I don't defer or do itx.response.defer())
        await InteractionResponse(itx).defer()

        # move the cache to the previous position
        self.state_cache.index -= 1

        await self.state_cache.load(itx.message)

    @discord.ui.button(emoji="\N{Black Right-Pointing Triangle}", disabled=True)
    async def next_state(self, itx: discord.Interaction, button: discord.ui.Button):
        await InteractionResponse(itx).defer()

        self.state_cache.index += 1

        await self.state_cache.load(itx.message)


class VanirPager(VanirView, Generic[VanirPagerT]):
    def __init__(
        self,
        user: discord.User,
        items: list[VanirPagerT],
        items_per_page: int,
        *,
        start_page: int = 0,
    ):
        super().__init__(user=user)
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


def _deco_factory(
    ctype: type[CommandT], name: str | None = None, **extras
) -> Callable[[Any], CommandT]:
    def inner(func: Any):
        cmd = ctype(func, name=name)
        cmd.extras = extras

        return cmd

    return inner


def vanir_command(
    name: str | None = None, *, hidden: bool = False
) -> Callable[[Any], commands.HybridCommand]:
    return _deco_factory(commands.HybridCommand, name, hidden=hidden)


def vanir_group(
    name: str | None = None, *, hidden: bool = False
) -> Callable[[Any], commands.HybridGroup]:
    return _deco_factory(commands.HybridGroup, name, hidden=hidden)


def cog_hidden(cls: type[VanirCog]):
    """A wrapper which sets the `VanirCog().hidden` flag to True when this class initializes"""
    original_init = cls.__init__

    @functools.wraps(original_init)
    def wrapper(self: VanirCog, bot: Vanir) -> None:
        original_init(self, bot)
        self.hidden = True

    cls.__init__ = wrapper
    return cls


def inherit(cmd: commands.Command):
    if cmd.parent is not None:
        parent: commands.HybridGroup = cmd.parent  # type: ignore
        cmd.hidden = parent.hidden
        cmd.extras = parent.extras
        cmd.checks = parent.checks

    return cmd


def vpar(
    desc: str,
    default: Any = empty,
    dis_default: str = empty,
    *,
    conv: Any = empty,
    dis_name: Any = empty,
):
    """A more compact `ext.commands.param`

    :param desc: The description of the parameter
    :param default: The default value of the parameter
    :param dis_default: What the default value appears as to the user
    :param conv: The converter class for the parameter
    :param dis_name: The name of the parameter which appears to the user"""
    return commands.param(
        description=desc,
        default=default,
        displayed_default=dis_default,
        converter=conv,
        displayed_name=dis_name,
    )
