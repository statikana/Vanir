import enum
import inspect
import logging
import math
from typing import TypeVar, Generic, Callable, Awaitable
from asyncio import iscoroutinefunction

import discord
import texttable
from discord import Interaction
from discord.ext import commands

from src.types.core import Vanir, VanirContext
from src.types.util import MessageState

empty = inspect.Parameter.empty

VanirPagerT = TypeVar("VanirPagerT")
CommandT = TypeVar("CommandT", bound=commands.Command)


class AcceptItx(enum.Enum):
    ANY = 0
    AUTHOR_ONLY = 1
    NOT_AUTHOR = 2


class VanirCog(commands.Cog):
    emoji = "\N{Black Question Mark Ornament}"

    def __init__(self, bot: Vanir):
        self.bot = bot
        self.hidden: bool = (
            False  # gets set to true if the class is decorated by @hidden
        )


class VanirView(discord.ui.View):
    def __init__(
        self,
        bot: Vanir,
        *,
        user: discord.User | None = None,
        accept_itx: (
            AcceptItx | Callable[[discord.Interaction], bool | Awaitable[bool]]
        ) = AcceptItx.AUTHOR_ONLY,
        timeout: float = 300,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
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
        bot: Vanir,
        *,
        user: discord.User | None = None,
        accept_itx: (
            AcceptItx | Callable[[discord.Interaction], bool | Awaitable[bool]]
        ) = AcceptItx.AUTHOR_ONLY,
        timeout: float = 300,
        items: list[discord.ui.Item] = None,
    ):
        super().__init__(bot, user=user, accept_itx=accept_itx, timeout=timeout)

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


class VanirModal(discord.ui.Modal):
    def __init__(self, bot: Vanir):
        super().__init__()
        self.bot = bot

    async def on_error(self, itx: discord.Interaction, error: Exception):
        self.bot.dispatch("command_error", itx, error)


class VanirPager(VanirView, Generic[VanirPagerT]):
    def __init__(
        self,
        bot: Vanir,
        user: discord.User,
        items: list[VanirPagerT],
        items_per_page: int,
        *,
        start_page: int = 0,
    ):
        super().__init__(bot, user=user)
        self.items = items
        self.items_per_page = items_per_page

        self.page = start_page
        if items_per_page <= 0:
            raise ValueError("items_per_page must be greater than 0")
        if len(items) <= 0:
            raise ValueError("items must not be empty")
        self.n_pages = math.ceil(len(items) / items_per_page)

        self.message: discord.Message | None = None

    @discord.ui.button(emoji="\N{Black Left-Pointing Double Triangle}", disabled=True)
    async def first(self, itx: discord.Interaction, button: discord.ui.Button):
        self.page = 0
        await self.update(itx, button)

    @discord.ui.button(emoji="\N{Leftwards Black Arrow}", disabled=True)
    async def back(self, itx: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self.update(itx, button)

    @discord.ui.button(emoji="\N{Cross Mark}", style=discord.ButtonStyle.danger)
    async def finish(self, itx: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

        await self.update(itx, button)
        self.stop()

    @discord.ui.button(emoji="\N{Black Rightwards Arrow}", disabled=True)
    async def next(self, itx: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self.update(itx, button)

    @discord.ui.button(emoji="\N{Black Right-Pointing Double Triangle}", disabled=True)
    async def last(self, itx: discord.Interaction, button: discord.ui.Button):
        self.page = self.n_pages - 1
        await self.update(itx, button)

    @discord.ui.button(label="GOTO", emoji="\N{Direct Hit}")
    async def custom(self, itx: discord.Interaction, button: discord.Button):
        modal = CustomPageModal(self.bot, itx, self)
        await itx.response.send_modal(modal)

    async def update(
        self, itx: discord.Interaction = None, source_button: discord.ui.Button = None
    ):
        """Called after every button press - enables and disables the appropriate buttons, and changes colors.
        Also fetches te new embed and edits the message and view to the new content."""
        if self.finish.disabled:
            await itx.response.edit_message(view=self)
            return
        if self.page == 0:
            VanirPager.disable(self.first, self.back)
        else:
            VanirPager.enable(self.first, self.back)

        if self.page == self.n_pages - 1:
            VanirPager.disable(self.next, self.last)
        else:
            VanirPager.enable(self.next, self.last)

        if source_button is not None:
            for i in self.children:
                if isinstance(i, discord.ui.Button):
                    if i == source_button:
                        i.style = discord.ButtonStyle.success
                    else:
                        if i.emoji.name != "\N{Cross Mark}":
                            i.style = discord.ButtonStyle.grey

        if self.message is not None:
            embed = await self.update_embed()
            if itx is not None:
                try:
                    await itx.response.edit_message(embed=embed, view=self)
                except discord.InteractionResponded:
                    await itx.edit_original_response(embed=embed, view=self)
            else:
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


class AutoTablePager(VanirPager):
    def __init__(
        self,
        bot: Vanir,
        user: discord.User,
        headers: list[str],
        rows: list[VanirPagerT],
        rows_per_page: int,
        *,
        dtypes: list[str],
        data_name: str = None,
    ):
        super().__init__(bot, user, rows, rows_per_page)
        self.headers = headers
        self.rows = self.items
        self.data_name = data_name
        self.dtypes = dtypes

    async def update_embed(self) -> discord.Embed:

        table = texttable.Texttable()
        table.header(self.headers)

        table.add_rows(
            self.rows[
                self.page * self.items_per_page : (self.page + 1) * self.items_per_page
            ],
            header=False,
        )
        table.set_deco(
            texttable.Texttable.HEADER
            | texttable.Texttable.BORDER
            | texttable.Texttable.VLINES
        )

        print(self.headers)

        table.set_cols_dtype(self.dtypes)

        if self.data_name is not None:
            title = f"{self.data_name}: Page {self.page+1} / {self.n_pages}"
        else:
            title = f"Page {self.page+1} / {self.n_pages}"

        embed = VanirContext.syn_embed(
            title=title, description=f"```\n{table.draw()}```", user=self.user
        )
        return embed


class CustomPageModal(VanirModal, title="Select Page"):
    def __init__(self, bot: Vanir, itx: discord.Interaction, view: VanirPager):
        super().__init__(bot)
        self.view = view
        self.page_input = discord.ui.TextInput(
            label=f"Please enter a page number between 1 and {view.n_pages}"
        )
        self.page_input.required = True
        self.add_item(self.page_input)

    async def on_submit(self, itx: discord.Interaction):
        value = self.page_input.value
        try:
            value = int(value)
        except TypeError:
            raise ValueError("Please enter a number")
        if not (1 <= value <= self.view.n_pages):
            raise ValueError(
                f"Please enter a page number between 1 and {self.view.n_pages}"
            )
        self.view.page = value - 1
        await self.view.update(itx=itx, source_button=VanirPager.custom)


class VanirHybridGroup(commands.HybridGroup):
    def command(self, aliases: list[str] = None):
        if aliases is None:
            aliases = []

        def inner(func):
            func = autopopulate(func)
            command = commands.HybridGroup.command(self, aliases=aliases)(func)
            command = inherit(command)
            return command

        return inner


def autopopulate(func):
    params = inspect.signature(func).parameters.copy()
    try:
        del params["self"]
    except KeyError:
        pass
    try:
        del params["ctx"]
    except KeyError:
        pass

    descriptions = {
        name: getattr(param.default, "description", None) or "no description"
        for name, param in params.items()
    }
    try:
        func.__discord_app_commands_param_description__.update(descriptions)
    except AttributeError:
        func.__discord_app_commands_param_description__ = descriptions

    logging.debug(f"Populated app_command descriptions: {descriptions}")
    return func


def inherit(cmd: commands.HybridCommand):
    if cmd.parent is not None:
        parent: commands.HybridGroup = cmd.parent  # type: ignore
        cmd.hidden = parent.hidden
        cmd.extras = parent.extras
        cmd.checks = parent.checks

    return cmd
