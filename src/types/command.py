from __future__ import annotations

import contextlib
import enum
import inspect
import io
import math
import re
from asyncio import iscoroutinefunction
from typing import Any, Awaitable, Callable, Generic, TypeVar

import discord
import texttable
from discord import Interaction
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from src.constants import EMOJIS, GITHUB_ROOT
from src.logging import book
from src.types.core import SFType, Vanir, VanirContext
from src.types.util import MessageState
from src.util.format import format_bool

VanirPagerT = TypeVar("VanirPagerT")
CommandT = TypeVar("CommandT", bound=commands.Command)


class AcceptItx(enum.Enum):
    ANY = 0
    AUTHOR_ONLY = 1
    NOT_AUTHOR = 2


class VanirCog(commands.Cog):
    emoji = "\N{BLACK QUESTION MARK ORNAMENT}"

    def __init__(self, bot: Vanir) -> None:
        self.bot = bot

        # gets set by @cog_hidden and @uses_sys_assets
        self.hidden: bool = False
        self.uses_sys_assets: bool = False

    async def cog_load(self) -> None:
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
    ) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.accept_itx = accept_itx
        self.user = user

    async def interaction_check(self, itx: Interaction, /) -> bool:
        async def inner():
            # ???
            if self.accept_itx in (
                AcceptItx.ANY,
                AcceptItx.AUTHOR_ONLY,
                AcceptItx.NOT_AUTHOR,
            ):
                if self.accept_itx == AcceptItx.ANY:
                    return True
                if self.user is None:
                    msg = (
                        "If view does not accept every interaction "
                        "and uses AcceptItx, .user must be set."
                    )
                    raise ValueError(
                        msg,
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
                    "You can't interact with this",
                    ephemeral=True,
                )
            except discord.InteractionResponded:
                await itx.followup.send("You can't interact with this", ephemeral=True)
            return False
        return True

    async def on_error(
        self,
        itx: Interaction,
        error: Exception,
        item: discord.ui.Item,
    ) -> None:
        self.bot.dispatch("command_error", itx, error)


class GitHubView(VanirView):
    def __init__(self, bot: Vanir, path: str = "") -> None:
        super().__init__(bot=bot)

        button = discord.ui.Button(
            url=f"{GITHUB_ROOT}/blob/main/{path}",
            emoji=str(EMOJIS["github"]),
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
        items: list[discord.ui.Item] | None = None,
    ) -> None:
        super().__init__(bot, user=user, accept_itx=accept_itx, timeout=timeout)

        if items is None:
            items = []

        for k in items:
            self.add_item(k)

        self.states: list[MessageState] = []
        self.state_index: int | None = None

        self.previous_state.disabled = True
        self.next_state.disabled = True

    @discord.ui.button(emoji=str(EMOJIS["b_arrow"]), row=1)
    async def previous_state(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.state_index is None:
            await self.collect(itx)
            self.state_index = len(self.states) - 2  # jump back behind the new cached
        else:
            self.state_index -= 1
        await self.update_to_state(itx)

    @discord.ui.button(emoji=str(EMOJIS["f_arrow"]), row=1)
    async def next_state(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.state_index += 1
        await self.update_to_state(itx)

    async def update_to_state(self, itx: discord.Interaction) -> None:
        await itx.response.defer()
        state: MessageState = self.states[self.state_index]

        for c in self.children:
            self.remove_item(c)

        for c in state.items:
            self.add_item(c)

        # because the buttons are all the same object, by changing
        # the object in memory here, it changes EVERYWHERE

        await self.check_buttons()

        await itx.message.edit(content=state.content, embeds=state.embeds, view=self)

    async def collect(self, itx: discord.Interaction) -> None:
        msg = itx.message
        self.states.append(MessageState(msg.content, msg.embeds, self.children))
        if self.state_index is not None:
            # we are already in the cache - remove whatever is ahead
            self.states = self.states[: self.state_index + 1]

        # we are now living outside of the cache, no index
        self.state_index = None
        await self.check_buttons()

    async def check_buttons(self) -> None:
        # at the back of the cache or there is no cache
        # (it is redundant to check for cache count here but meh)
        self.previous_state.disabled = self.state_index == 0 or len(self.states) == 0
        self.next_state.disabled = (
            self.state_index is None or self.state_index == len(self.states) - 1
        )

    def auto_add_item(self, item: discord.ui.Item) -> None:
        back, fwd = self.previous_state, self.next_state
        self.remove_item(back)
        self.remove_item(fwd)
        next_row = (
            max(item.row for item in [*self.children, item]) if self.children else 0
        ) + 1
        if next_row >= 5:
            msg = "Too many rows - max 4 with AutoCachedView"
            raise ValueError(msg)
        back.row = next_row
        fwd.row = next_row
        super().add_item(item)
        super().add_item(back)
        super().add_item(fwd)


class VanirModal(discord.ui.Modal):
    def __init__(self, bot: Vanir, *, title: str = discord.utils.MISSING) -> None:
        super().__init__(title=title)
        self.bot = bot

    async def on_error(self, itx: discord.Interaction, error: Exception) -> None:
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
        include_spacer_image: bool = False
    ) -> None:
        super().__init__(bot, user=user)
        self.items = items
        self.items_per_page = items_per_page
        self.include_spacer_image = include_spacer_image

        self.page = start_page
        if items_per_page <= 0:
            msg = "items_per_page must be greater than 0"
            raise ValueError(msg)
        if len(items) <= 0:
            msg = "items must not be empty"
            raise ValueError(msg)
        self.n_pages = math.ceil(len(items) / items_per_page)

        self.message: discord.Message | None = None

    @discord.ui.button(
        emoji=str(EMOJIS["bb_arrow"]),
        disabled=True,
    )
    async def first(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = 0
        await self.update(itx, button)

    @discord.ui.button(
        emoji=str(EMOJIS["b_arrow"]),
        disabled=True,
    )
    async def back(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        self.page -= 1
        await self.update(itx, button)

    @discord.ui.button(
        emoji=str(EMOJIS["close"]),
        style=discord.ButtonStyle.danger,
        custom_id="constant-style:finish",
    )
    async def close(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

        await self.update(itx, button)
        self.stop()

    @discord.ui.button(
        emoji=str(EMOJIS["f_arrow"]),
        disabled=True,
    )
    async def next(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        self.page += 1
        await self.update(itx, button)

    @discord.ui.button(
        emoji=str(EMOJIS["ff_arrow"]),
        disabled=True,
    )
    async def last(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        self.page = self.n_pages - 1
        await self.update(itx, button)

    @discord.ui.button(
        label="GO TO",
        emoji="\N{DIRECT HIT}",
        custom_id="constant-style:goto",
        style=discord.ButtonStyle.blurple,
    )
    async def go_to_page(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        modal = CustomPageModal(self.bot, itx, self)
        await itx.response.send_modal(modal)

    async def update(
        self,
        itx: discord.Interaction = None,
        source_button: discord.ui.Button = None,
        update_content: bool = True,
    ) -> None:
        """
        Called after every button press - enables and disables the
        appropriate buttons, and changes colors.

        Also fetches the new embed and edits the message and view to the new content.
        """
        if itx is not None:
            self.message = itx.message
        if self.close.disabled:
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

        self.close.label = f"Page {self.page+1}/{self.n_pages} [{len(self.items)}]"

        if source_button is not None:
            source_button.style = discord.ButtonStyle.success
            for btn in {self.first, self.back, self.next, self.last} - {source_button}:
                btn.style = discord.ButtonStyle.grey

        if update_content:
            if self.message is not None:
                embed = await self.update_embed()
                if self.include_spacer_image:
                    file = discord.File("assets/spacer.png", filename="spacer.png")
                    embed.set_image(url="attachment://spacer.png")
                else:
                    file = None

                if itx is not None:
                    try:
                        await itx.response.edit_message(embed=embed, view=self, attachments=[file])
                    except discord.InteractionResponded:
                        await itx.edit_original_response(embed=embed, view=self, file=file)
                else:
                    await self.message.edit(embed=embed, view=self, file=file)
            else:
                book.warning(
                    f"Pager has no message attached "
                    f"(VanirPagerT: {VanirPagerT}), cannot update message",
                )

    async def update_embed(self) -> discord.Embed:
        """To be implemented by children classes."""
        raise NotImplementedError

    @staticmethod
    def enable(*buttons: discord.ui.Button) -> None:
        for button in buttons:
            button.disabled = False

    @staticmethod
    def disable(*buttons: discord.ui.Button) -> None:
        for button in buttons:
            button.disabled = True


class AutoTablePager(VanirPager):
    def __init__(
        self,
        bot: Vanir,
        user: discord.User,
        *,
        headers: list[str],
        rows: list[VanirPagerT],
        rows_per_page: int,
        dtypes: list[str] | None = None,
        data_name: str | None = None,
        include_hline: bool = False,
        row_key: Callable[[VanirPagerT], list] | None = None,
        start_page: int = 0,
        include_spacer_image: bool = False
    ) -> None:
        super().__init__(bot, user, rows, rows_per_page, start_page=start_page, include_spacer_image=include_spacer_image)
        self.headers = headers
        self.rows = self.items
        self.data_name = data_name
        self.dtypes = dtypes
        self.include_hline = include_hline
        self.row_key = row_key or (lambda x: x)

    @property
    def current(self) -> list[VanirPagerT]:
        return self.rows[
            self.page * self.items_per_page : (self.page + 1) * self.items_per_page
        ]

    async def update_embed(self) -> discord.Embed:
        table = texttable.Texttable(61)
        table.header(self.headers)

        table.add_rows(
            (self.row_key(r) for r in self.current),
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

        text = text.replace("True", format_bool(True) + " ").replace(
            "False",
            format_bool(False) + "   ",
        )
        return VanirContext.syn_embed(
            title=title,
            description=f"```ansi\n{text}\n```",
            user=self.user,
        )

    def draw_image(self, text: str) -> tuple[discord.Embed, discord.File]:
        font_size = 50
        width = len(text[: text.index("\n")]) * font_size
        height = (text.strip("\n").count("\n") + 1) * font_size

        image = Image.new("RGBA", (width, height), (0, 0, 0))

        font = ImageFont.truetype("assets/Monospace.ttf", size=font_size)
        draw = ImageDraw.Draw(image)

        false = [m.start() for m in re.finditer(r"False", text)]
        true = [m.start() for m in re.finditer(r"True", text)]

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
    def __init__(self, bot: Vanir, itx: discord.Interaction, view: VanirPager) -> None:
        super().__init__(bot)
        self.view = view
        self.page_input = discord.ui.TextInput(
            label=f"Please enter a page number between 1 and {view.n_pages}",
        )
        self.page_input.required = True
        self.add_item(self.page_input)

    async def on_submit(self, itx: discord.Interaction) -> None:
        value = self.page_input.value
        try:
            value = int(value)
        except TypeError as exc:
            msg = "Please enter a number"
            raise ValueError(msg) from exc
        if not 1 <= value <= self.view.n_pages:
            msg = f"Please enter a page number between 1 and {self.view.n_pages}"
            raise ValueError(
                msg,
            )
        self.view.page = value - 1
        await self.view.update(itx=itx, source_button=VanirPager.go_to_page)


class CloseButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.danger,
            label="Close",
            emoji=str(EMOJIS["close"]),
        )

    async def callback(self, itx: discord.Interaction) -> None:
        await itx.message.delete()


class VanirHybridCommand(commands.HybridCommand):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.sf_receiver: SFType | None = kwargs.pop("sf_receiver", None)
        super().__init__(*args, **kwargs)


class VanirHybridGroup(commands.HybridGroup):
    def command(
        self,
        *,
        name: str | None = None,
        aliases: list[str] | None = None,
    ) -> Callable[[Any], VanirHybridCommand]:
        if aliases is None:
            aliases = []

        def inner(func: Callable):
            func = autopopulate_descriptions(func)
            command = commands.HybridGroup.command(self, name=name, aliases=aliases)(
                func,
            )
            return inherit(command)

        return inner


def autopopulate_descriptions(func: Callable) -> Callable:
    params = inspect.signature(func).parameters.copy()
    with contextlib.suppress(KeyError):
        del params["self"]
    with contextlib.suppress(KeyError):
        del params["ctx"]

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


def inherit(cmd: commands.HybridCommand) -> commands.HybridCommand:
    if cmd.parent is not None:
        parent: commands.HybridGroup = cmd.parent
        cmd.hidden = parent.hidden
        cmd.extras = parent.extras
        cmd.checks = parent.checks

    return cmd


def vanir_command(
    *,
    name: str | None = None,
    hidden: bool = False,
    aliases: list[str] | None = None,
    sf_receiver: SFType | None = None,
) -> Callable[[Any], commands.HybridCommand]:
    if aliases is None:
        aliases = []

    def inner(func: Any):
        func = autopopulate_descriptions(func)
        cmd = VanirHybridCommand(
            func,
            aliases=aliases,
            name=name or discord.utils.MISSING,
            sf_receiver=sf_receiver,
        )
        cmd.hidden = hidden
        cmd.sf_receiver = sf_receiver
        return inherit(cmd)

    return inner


def vanir_group(
    hidden: bool = False,
    aliases: list[str] | None = None,
    invoke_without_subcommand: bool = True,
) -> Callable[[Any], VanirHybridGroup]:
    if aliases is None:
        aliases = []

    def inner(func: Any):
        return VanirHybridGroup(
            func,
            aliases=aliases,
            with_app_command=not hidden,
            hidden=hidden,
            invoke_without_subcommand=invoke_without_subcommand,
        )

    return inner


def uses_sys_assets(cls: VanirCog) -> VanirCog:
    cls.uses_sys_assets = True
    return cls


BotObjectT = TypeVar("BotObjectT", VanirHybridCommand, VanirHybridGroup, VanirCog)
