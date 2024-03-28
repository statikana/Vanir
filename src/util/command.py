from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from discord.app_commands import Choice
from discord.ext import commands

import config
from src import constants
from src.types.media import ImageInterface, MediaInfo, MediaInterface, VideoInterface
from src.util import format
from src.util.parse import find_ext

if TYPE_CHECKING:
    import inspect

    import discord

    from src.types.command import (
        VanirCog,
    )
    from src.types.core import Vanir, VanirContext

if config.use_system_assets:
    from wand.image import Image


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
    if get_origin(ptype) is Union:
        ptype = get_args(ptype)[0]

    if hasattr(ptype, "min"):  # this is a .Range
        rtype_name = ptype.annotation.__name__  # eg <class 'int'> -> int
        range_min = ptype.min
        range_max = ptype.max

        if rtype_name == "int":
            rtype_name = "integer"
        if rtype_name == "float":
            rtype_name = "decimal"

        if range_min is None:
            return f"{rtype_name} <= {range_max}"
        if range_max is None:
            return f"{rtype_name} >= {range_min}"
        return f"{range_min} <= {rtype_name} <= {range_max}"

    if ptype is int:
        return "integer"
    if ptype is float:
        return "decimal"
    if ptype is str:
        return "string"
    if ptype is bool:
        return "boolean"
    if not (strrep := str(ptype)).startswith("<class"):
        return strrep
    return getattr(ptype, "__name__", strrep)


async def get_media_info(media: MediaInterface) -> MediaInfo | None:
    blob = await media.read()
    if isinstance(media, ImageInterface):
        img = Image(blob=blob)
        return MediaInfo(f"image/{img.format}", img.length_of_bytes)
    if isinstance(media, VideoInterface):
        ext = find_ext(media.url)
        return MediaInfo(f"image/{ext}", len(blob))
    return None


async def send_file(
    source_cmd: commands.HybridCommand,
    msg: discord.Message,
    media: MediaInterface,
) -> None:
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
        value=f"`{format.fmt_size(new_info.size, format.Convention.BINARY)}` **|** "
        f"`{format.fmt_size(new_info.size, format.Convention.DECIMAL)}`",
        inline=False,
    )

    await msg.edit(embed=embed, attachments=[await media.to_file()])


async def assure_working(ctx: VanirContext, media: MediaInterface) -> discord.Message:
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
        value=f"`{format.fmt_size(media.initial_info.size, format.Convention.BINARY)}` **|** "
        f"`{format.fmt_size(media.initial_info.size, format.Convention.DECIMAL)}`",
        inline=False,
    )
    return await ctx.reply(embed=embed)


def cog_hidden(cls: type[VanirCog]) -> type[VanirCog]:
    """Set the `VanirCog().hidden` flag to True when this class initializes,."""
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


def safe_default(
    arg: Any,
    /,
    ctx: VanirContext | None = None,
) -> Any:
    if isinstance(arg, commands.Parameter):
        if ctx is not None:
            return arg.get_default(ctx)
        return arg.default
    return arg


async def langcode_autocomplete(
    _itx: discord.Interaction,
    current: str,
) -> list[Choice]:
    options = [
        Choice(name=f"{v} [{k}]", value=k) for k, v in constants.LANGUAGE_NAMES.items()
    ][:25]
    return sorted(
        filter(lambda c: current.lower() in c.name.lower(), options),
        key=lambda c: c.name,
    )
