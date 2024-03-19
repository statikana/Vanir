import asyncio
import enum
import inspect
import io
import logging
import math
import re
from asyncio import iscoroutinefunction
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, TypeVar

import discord
import texttable
from discord import Interaction
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from src.constants import GITHUB_ROOT
from src.logging import book
from src.types.core import Vanir, VanirContext
from src.types.util import MessageState
from src.util.fmt import fmt_bool

VanirPagerT = TypeVar("VanirPagerT")
CommandT = TypeVar("CommandT", bound=commands.Command)


class AcceptItx(enum.Enum):
    ANY = 0
    AUTHOR_ONLY = 1
    NOT_AUTHOR = 2


class VanirCog(commands.Cog):
    emoji = "\N{BLACK QUESTION MARK ORNAMENT}"

    def __init__(self, bot: Vanir):
        self.bot = bot
        self.hidden: bool = (
            False  # gets set to true if the class is decorated by @hidden
        )

    async def cog_load(self):
        book.info(f"{self.__class__.__name__} loaded")


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
                        "If view does not accept every interaction "
                        "and uses AcceptItx, .user must be set."
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


class GitHubView(VanirView):
    def __init__(self, bot: Vanir, path: str = ""):
        super().__init__(bot=bot)

        button = discord.ui.Button(
            url=f"{GITHUB_ROOT}/blob/main/{path}",
            emoji="\N{SQUID}",
            label="View on GitHub",
        )
        self.add_item(button)


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

    @discord.ui.button(emoji="\N{BLACK LEFT-POINTING TRIANGLE}", row=1)
    async def previous_state(self, itx: discord.Interaction, button: discord.ui.Button):
        if self.state_index is None:
            await self.collect(itx)
            self.state_index = len(self.states) - 2  # jump back behind the new cached
        else:
            self.state_index -= 1
        await self.update_to_state(itx)

    @discord.ui.button(emoji="\N{BLACK RIGHT-POINTING TRIANGLE}", row=1)
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

        # because the buttons are all the same object, by changing
        # the object in memory here, it changes EVERYWHERE

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
        # at the back of the cache or there is no cache
        # (it is redundant to check for cache count here but meh)
        self.previous_state.disabled = self.state_index == 0 or len(self.states) == 0
        self.next_state.disabled = (
            self.state_index is None or self.state_index == len(self.states) - 1
        )

    def auto_add_item(self, item: discord.ui.Item):
        back, fwd = self.previous_state, self.next_state
        self.remove_item(back)
        self.remove_item(fwd)
        next_row = (
            max(item.row for item in self.children + [item]) if self.children else 0
        ) + 1
        if next_row >= 5:
            raise ValueError("Too many rows - max 4 with AutoCachedView")
        back.row = next_row
        fwd.row = next_row
        super().add_item(item)
        super().add_item(back)
        super().add_item(fwd)


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

        self.cur_page = start_page
        if items_per_page <= 0:
            raise ValueError("items_per_page must be greater than 0")
        if len(items) <= 0:
            raise ValueError("items must not be empty")
        self.n_pages = math.ceil(len(items) / items_per_page)

        self.message: discord.Message | None = None

    @discord.ui.button(emoji="\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}", disabled=True)
    async def first(self, itx: discord.Interaction, button: discord.ui.Button):
        self.cur_page = 0
        await self.update(itx, button)

    @discord.ui.button(emoji="\N{LEFTWARDS BLACK ARROW}", disabled=True)
    async def back(self, itx: discord.Interaction, button: discord.ui.Button):
        self.cur_page -= 1
        await self.update(itx, button)

    @discord.ui.button(
        emoji="\N{HEAVY MULTIPLICATION X}",
        style=discord.ButtonStyle.danger,
        custom_id="constant-style:finish",
    )
    async def close(self, itx: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

        await self.update(itx, button)
        self.stop()

    @discord.ui.button(emoji="\N{BLACK RIGHTWARDS ARROW}", disabled=True)
    async def next(self, itx: discord.Interaction, button: discord.ui.Button):
        self.cur_page += 1
        await self.update(itx, button)

    @discord.ui.button(emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}", disabled=True)
    async def last(self, itx: discord.Interaction, button: discord.ui.Button):
        self.cur_page = self.n_pages - 1
        await self.update(itx, button)

    @discord.ui.button(
        label="GO TO",
        emoji="\N{DIRECT HIT}",
        custom_id="constant-style:custom",
        style=discord.ButtonStyle.blurple,
    )
    async def go_to_page(self, itx: discord.Interaction, button: discord.Button):
        modal = CustomPageModal(self.bot, itx, self)
        await itx.response.send_modal(modal)

    async def update(
        self,
        itx: discord.Interaction = None,
        source_button: discord.ui.Button = None,
        update_content: bool = True,
    ):
        """Called after every button press - enables and disables the
        appropriate buttons, and changes colors. Also fetches the
        new embed and edits the message and view to the new content."""
        if self.close.disabled:
            await itx.response.edit_message(view=self)
            return
        if self.cur_page == 0:
            VanirPager.disable(self.first, self.back)
        else:
            VanirPager.enable(self.first, self.back)

        if self.cur_page == self.n_pages - 1:
            VanirPager.disable(self.next, self.last)
        else:
            VanirPager.enable(self.next, self.last)

        self.close.label = f"Page {self.cur_page+1}/{self.n_pages}"

        if source_button is not None:
            for i in self.children:
                if isinstance(i, discord.ui.Button):
                    if i == source_button:
                        i.style = discord.ButtonStyle.success
                    else:
                        if not (i.custom_id or "").startswith("constant-style"):
                            i.style = discord.ButtonStyle.grey

        if update_content:
            if self.message is not None:
                embed = await self.update_embed()

                if isinstance(embed, tuple):
                    embed, file = embed
                else:
                    embed, file = embed, None
                if itx is not None:
                    try:
                        await itx.response.edit_message(
                            embed=embed, view=self, attachments=[file] if file else []
                        )
                    except discord.InteractionResponded:
                        await itx.edit_original_response(
                            embed=embed, view=self, attachments=[file] if file else []
                        )
                else:
                    await self.message.edit(
                        embed=embed, view=self, attachments=[file] if file else []
                    )
            else:
                book.warning(
                    f"Pager has no message attached "
                    f"(VanirPagerT: {VanirPagerT}), cannot update message"
                )

    async def update_embed(self) -> discord.Embed | tuple[discord.Embed, discord.File]:
        """To be implemented by children classes"""
        raise NotImplementedError

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
        *,
        as_image: bool = True,
        headers: list[str],
        rows: list[VanirPagerT],
        rows_per_page: int,
        dtypes: list[str] = None,
        data_name: str = None,
        include_hline: bool = False,
    ):
        super().__init__(bot, user, rows, rows_per_page)
        self.as_image = as_image
        self.headers = headers
        self.rows = self.items
        self.data_name = data_name
        self.dtypes = dtypes
        self.include_hline = include_hline

    async def update_embed(self):
        table = texttable.Texttable(61)
        table.header(self.headers)

        table.add_rows(
            self.rows[
                self.cur_page * self.items_per_page : (self.cur_page + 1)
                * self.items_per_page
            ],
            header=False,
        )
        deco = (
            texttable.Texttable.HEADER
            | texttable.Texttable.BORDER
            | texttable.Texttable.VLINES
        )
        if self.include_hline:
            deco |= texttable.Texttable.HLINES

        table.set_deco(deco)

        if self.dtypes:
            table.set_cols_dtype(self.dtypes)

        title = self.data_name or None

        text = table.draw()

        if self.as_image:
            embed, file_ = await asyncio.to_thread(self.draw_image, text, title)
        else:
            text = text.replace("True", fmt_bool(True) + " ").replace(
                "False", fmt_bool(False) + "   "
            )
            embed, file_ = (
                VanirContext.syn_embed(
                    title=title, description=f"```ansi\n{text}\n```", user=self.user
                ),
                None,
            )

        return embed, file_

    def draw_image(self, text: str) -> tuple[discord.Embed, discord.File]:
        font_size = 50
        width = len(text[: text.index("\n")]) * font_size
        height = (text.strip("\n").count("\n") + 1) * font_size

        image = Image.new("RGBA", (width, height), (0, 0, 0))

        font = ImageFont.truetype("assets/Monospace.ttf", size=font_size)
        draw = ImageDraw.Draw(image)

        false = [m.start() for m in re.finditer(r"False", text)]
        true = [m.start() for m in re.finditer(r"True", text)]

        # changes = set(true)

        pos = [0, 0]

        for i, char in enumerate(text):
            if char == "\n":
                pos = [0, pos[1] + font_size]
                continue

            color = (255, 255, 255)

            for s in true:
                if 0 <= i - s <= 3:
                    color = (0, 255, 0)

            for s in false:
                if 0 <= i - s <= 4:
                    color = (255, 0, 0)

            draw.text(
                (pos[0], pos[1]),
                char,
                font=font,
                stroke_fill=color,
                stroke_width=1,
                spacing=4,
            )

            pos[0] += font_size

        buffer = io.BytesIO()
        image.save(buffer, "png")
        buffer.seek(0)
        file = discord.File(buffer, filename="table.png")

        embed = VanirContext.syn_embed("something", user=self.user)
        embed.set_image(url="attachment://table.png")
        return embed, file


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
        except TypeError as exc:
            raise ValueError("Please enter a number") from exc
        if not 1 <= value <= self.view.n_pages:
            raise ValueError(
                f"Please enter a page number between 1 and {self.view.n_pages}"
            )
        self.view.cur_page = value - 1
        await self.view.update(itx=itx, source_button=VanirPager.go_to_page)


class TaskIDConverter(commands.Converter[int]):
    async def convert(self, ctx: VanirContext, argument: str) -> int:
        if argument.isdigit():
            todo = await ctx.bot.db_todo.get_by_id(int(argument))
            if todo is not None:
                return int(argument)

        task_id = await ctx.bot.db_todo.get_by_name(ctx.author.id, argument)
        if task_id is None:
            raise commands.CommandInvokeError(
                ValueError("Could not find task with name or ID " + argument)
            )
        return task_id


@dataclass
class ModalField:
    label: str
    style: discord.TextStyle = discord.TextStyle.short
    default: str | None = None
    placeholder: str | None = None
    value: str | None = None
    required: bool = True


class VanirHybridCommand(commands.Command):
    pass


class VanirHybridGroup(commands.HybridGroup):
    def command(self, *, name: str = None, aliases: list[str] = None):
        if aliases is None:
            aliases = []

        def inner(func):
            func = autopopulate_descriptions(func)
            command = commands.HybridGroup.command(self, name=name, aliases=aliases)(
                func
            )
            command = inherit(command)
            return command

        return inner


def autopopulate_descriptions(func):
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

    book.debug(f"Populated app_command descriptions: {descriptions}")
    return func


def inherit(cmd: commands.HybridCommand):
    if cmd.parent is not None:
        parent: commands.HybridGroup = cmd.parent  # type: ignore
        cmd.hidden = parent.hidden
        cmd.extras = parent.extras
        cmd.checks = parent.checks

    return cmd


def vanir_command(
    hidden: bool = False, aliases: list[str] = None
) -> Callable[[Any], commands.HybridCommand]:
    if aliases is None:
        aliases = []

    def inner(func: Any):
        func = autopopulate_descriptions(func)
        cmd = commands.HybridCommand(func, aliases=aliases)
        cmd.hidden = hidden
        cmd = inherit(cmd)

        return cmd

    return inner


def vanir_group(
    hidden: bool = False,
    aliases: list[str] = None,
    invoke_without_subcommand: bool = True,
) -> Callable[[Any], VanirHybridGroup]:
    if aliases is None:
        aliases = []

    def inner(func: Any):
        cmd = VanirHybridGroup(
            func,
            aliases=aliases,
            with_app_command=not hidden,
            hidden=hidden,
            invoke_without_subcommand=invoke_without_subcommand,
        )

        return cmd

    return inner


BotObjectT = TypeVar("BotObjectT", VanirHybridCommand, VanirHybridGroup, VanirCog)
