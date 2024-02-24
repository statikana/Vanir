import enum
import functools
import inspect
import logging
import math
from typing import TypeVar, Generic, Callable, Any, Awaitable
from asyncio import iscoroutinefunction

import discord
from discord import Interaction
from discord.ext import commands

from src.types.core import Vanir
from src.types.util import MessageState

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
        accept_itx: (
            AcceptItx | Callable[[discord.Interaction], bool | Awaitable[bool]]
        ) = AcceptItx.AUTHOR_ONLY,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.accept_itx = accept_itx
        self.user = user

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


class AutoCachedView(VanirView):
    def __init__(
        self,
        *,
        user: discord.User | None = None,
        accept_itx: (
            AcceptItx | Callable[[discord.Interaction], bool | Awaitable[bool]]
        ) = AcceptItx.AUTHOR_ONLY,
        timeout: float = 300,
        items: list[discord.ui.Item] = None,
    ):
        super().__init__(user=user, accept_itx=accept_itx, timeout=timeout)

        if items is None:
            items = []

        for k in items:
            self.add_item(k)

        self.states: list[MessageState] = []
        self.state_index: int | None = None

        self.previous_state.disabled = True
        self.next_state.disabled = True

    @discord.ui.button(emoji="\N{Black Left-Pointing Triangle}", row=1)
    async def previous_state(self, itx: discord.Interaction, button: discord.ui.Button):

        if self.state_index is None:
            await self.collect(itx)
            self.state_index = len(self.states) - 2  # jump back behind the new cached
        else:
            self.state_index -= 1
        await self.update_to_state(itx)

    @discord.ui.button(emoji="\N{Black Right-Pointing Triangle}", row=1)
    async def next_state(self, itx: discord.Interaction, button: discord.ui.Button):

        self.state_index += 1
        await self.update_to_state(itx)

    async def update_to_state(self, itx: discord.Interaction):
        await itx.response.defer()
        state = self.states[self.state_index]

        for c in self.children:
            self.remove_item(c)

        for c in state.items:
            self.add_item(c)

        # because the buttons are all the same object, by changing the object in memory here, it changes EVERYWHERE

        await self.check_buttons()

        await itx.message.edit(content=state.content, embeds=state.embeds, view=self)

    async def collect(self, itx: discord.Interaction):
        msg = itx.message
        self.states.append(MessageState(msg.content, msg.embeds, self.children))
        if self.state_index is not None:
            # we are already in the cache - remove whatever is ahead
            self.states = self.states[: self.state_index + 1]

        # we are now living outside of the cache, no index
        self.state_index = None
        await self.check_buttons()

    async def check_buttons(self):
        # at the back of the cache or there is no cache (it is redundant to check for cache count here but meh)
        self.previous_state.disabled = self.state_index == 0 or len(self.states) == 0
        self.next_state.disabled = (
            self.state_index is None or self.state_index == len(self.states) - 1
        )


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
