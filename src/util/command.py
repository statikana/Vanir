import functools
import inspect
from typing import Callable, Any

import discord
from discord.app_commands import Choice
from discord.ext import commands

from src.types.command import (
    VanirHybridGroup,
    VanirCog,
    autopopulate_add_descriptions,
    inherit,
)
from src.types.core import VanirContext, Vanir
from src.types.media import ImageInterface, MediaInfo, MediaInterface, VideoInterface
from wand.image import Image

from src.constants import LANGUAGE_INDEX
from src.util.fmt import fmt_size
from src.util.parse import Convention, find_ext


def discover_group(group: commands.Group) -> set[commands.Command]:
    end = group.commands
    for s in end:
        if isinstance(s, commands.Group):
            end.update(s.commands)
        else:
            end.add(s)

    return end


def discover_cog(cog: commands.Cog) -> set[commands.Command]:
    cs = cog.get_commands()
    end = set()
    for command in cs:
        if isinstance(command, commands.Group):
            end.update(discover_group(command))
        else:
            end.add(command)

    return end


def get_display_cogs(bot: commands.Bot) -> list[commands.Cog]:
    return [
        c
        for c in bot.cogs.values()
        if not getattr(c, "hidden", False) and c.qualified_name.lower() != "jishaku"
    ]


def get_param_annotation(param: inspect.Parameter) -> str:
    ptype = param.annotation

    if str(ptype).endswith(">"):
        return ptype.__name__

    if hasattr(ptype, "min"):  # this is a .Range
        rtype_name = getattr(ptype, "annotation").__name__  # eg <class 'int'> -> int
        range_min = getattr(ptype, "min")
        range_max = getattr(ptype, "max")

        if rtype_name == "int":
            rtype_name = "integer"
        if rtype_name == "float":
            rtype_name = "decimal"

        if range_min is None:
            return f"{rtype_name} <= {range_max}"
        elif range_max is None:
            return f"{rtype_name} >= {range_min}"
        else:
            return f"{range_min} <= {rtype_name} <= {range_max}"
    return str(ptype)


async def langcode_autocomplete(itx: discord.Interaction, current: str):
    options = [Choice(name=f"{v} [{k}]", value=k) for k, v in LANGUAGE_INDEX.items()][
        :25
    ]
    options = sorted(
        filter(lambda c: current.lower() in c.name.lower(), options),
        key=lambda c: c.name,
    )
    return options


async def get_media_info(media: MediaInterface):
    blob = await media.read()
    if isinstance(media, ImageInterface):
        img = Image(blob=blob)
        return MediaInfo(f"image/{img.format}", img.length_of_bytes)
    elif isinstance(media, VideoInterface):
        ext = find_ext(media.url)
        return MediaInfo(f"image/{ext}", len(blob))


async def send_file(
    ctx: VanirContext,
    source_cmd: commands.HybridCommand,
    msg: discord.Message,
    media: MediaInterface,
):
    embed = msg.embeds[0]
    embed.title = f"{source_cmd.qualified_name.title()} Completed"
    new_info = await get_media_info(media)
    embed.add_field(
        name="File MIME Type [Output]",
        value=f"`{new_info.mime_type}` [Supported]",
        inline=False,
    )
    embed.add_field(
        name="File Size [Output]",
        value=f"`{fmt_size(new_info.size, Convention.BINARY)}` **|** `{fmt_size(new_info.size, Convention.DECIMAL)}`",
        inline=False,
    )

    await msg.edit(embed=embed, attachments=[await media.to_file()])


async def assure_working(ctx: VanirContext, media: MediaInterface):
    embed = ctx.embed(
        title="... working",
    )
    embed.add_field(
        name="File MIME Type [Input]",
        value=f"`{media.initial_info.mime_type}` [Supported]",
        inline=False,
    )
    embed.add_field(
        name="File Size [Input]",
        value=f"`{fmt_size(media.initial_info.size, Convention.BINARY)}` **|** `{fmt_size(media.initial_info.size, Convention.DECIMAL)}`",
        inline=False,
    )
    return await ctx.reply(embed=embed)


def vanir_command(
    hidden: bool = False, aliases: list[str] = None
) -> Callable[[Any], commands.HybridCommand]:
    if aliases is None:
        aliases = []

    def inner(func: Any):
        func = autopopulate_add_descriptions(func)
        cmd = commands.HybridCommand(func, aliases=aliases)
        cmd.hidden = hidden
        cmd = inherit(cmd)

        return cmd

    return inner


def vanir_group(
    hidden: bool = False, aliases: list[str] = None
) -> Callable[[Any], VanirHybridGroup]:
    if aliases is None:
        aliases = []

    def inner(func: Any):
        cmd = VanirHybridGroup(
            func, aliases=aliases, with_app_command=not hidden, hidden=hidden
        )

        return cmd

    return inner


def cog_hidden(cls: type[VanirCog]):
    """A wrapper which sets the `VanirCog().hidden` flag to True when this class initializes"""
    original_init = cls.__init__

    @functools.wraps(original_init)
    def wrapper(self: VanirCog, bot: Vanir) -> None:
        original_init(self, bot)
        self.hidden = True

        for c in dir(self):
            if isinstance(c := getattr(self, c), commands.Command):
                c.hidden = True
                c.with_app_command = False

    cls.__init__ = wrapper
    return cls
