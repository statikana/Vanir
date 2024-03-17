import functools
import inspect
from typing import Any

import discord
from discord.app_commands import Choice
from discord.ext import commands

import config
from src import constants
from src.types.command import (
    VanirCog,
)
from src.types.core import Vanir, VanirContext
from src.types.media import ImageInterface, MediaInfo, MediaInterface, VideoInterface
from src.util import fmt

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
        if range_max is None:
            return f"{rtype_name} >= {range_min}"
        return f"{range_min} <= {rtype_name} <= {range_max}"
    return str(ptype)


async def get_media_info(media: MediaInterface):
    blob = await media.read()
    if isinstance(media, ImageInterface):
        img = Image(blob=blob)
        return MediaInfo(f"image/{img.format}", img.length_of_bytes)
    if isinstance(media, VideoInterface):
        ext = fmt.find_ext(media.url)
        return MediaInfo(f"image/{ext}", len(blob))


async def send_file(
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
        value=f"`{fmt.fmt_size(new_info.size, fmt.Convention.BINARY)}` **|** "
        f"`{fmt.fmt_size(new_info.size, fmt.Convention.DECIMAL)}`",
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
        value=f"`{fmt.fmt_size(media.initial_info.size, fmt.Convention.BINARY)}` **|** "
        f"`{fmt.fmt_size(media.initial_info.size, fmt.Convention.DECIMAL)}`",
        inline=False,
    )
    return await ctx.reply(embed=embed)


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


def safe_default(arg: Any | commands.Parameter) -> Any:
    if isinstance(arg, commands.Parameter):
        return arg.default
    return arg


async def langcode_autocomplete(_itx: discord.Interaction, current: str):
    options = [
        Choice(name=f"{v} [{k}]", value=k) for k, v in constants.LANGUAGE_NAMES.items()
    ][:25]
    options = sorted(
        filter(lambda c: current.lower() in c.name.lower(), options),
        key=lambda c: c.name,
    )
    return options
