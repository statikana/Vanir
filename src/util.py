import inspect
import math
from datetime import datetime
from typing import Any
import re
from enum import Enum
from urllib.parse import urlparse

import discord
from discord.ext import commands
from wand.image import Image

from src.types.core import VanirContext
from src.types.media import MediaConverter, MediaInfo, MediaInterface, ImageInterface, VideoInterface

from assets.color_db import COLORS


class Convention(Enum):
    DECIMAL = 0
    BINARY = 1


def ensure_slug(slug: str) -> str:
    return re.sub(r"[^a-z0-9\-]", "", slug).lower().strip(" .-")


def format_dict(
    data: dict[Any, Any], miss_keys: list[Any] = None, linesplit: bool = False
) -> str:
    if miss_keys is None:
        miss_keys = []
    lines: list[str] = []
    for k, v in data.items():
        if k not in miss_keys:
            v_str = f"*{v}*"
        else:
            v_str = f"{v}"
        if linesplit:
            lines.append(f"**{k}**:\n. . . {v_str}")
        else:
            lines.append(f"**{k}**: {v_str}")

    return "\n".join(lines)


def readable_iso8601(date: datetime) -> str:
    return date.strftime("%H:%M, %d %b, %Y")


def discover_cog(cog: commands.Cog) -> set[commands.Command]:
    cs = cog.get_commands()
    end = set()
    for command in cs:
        if isinstance(command, commands.Group):
            end.update(discover_group(command))
        else:
            end.add(command)

    return end


def discover_group(group: commands.Group) -> set[commands.Command]:
    end = group.commands
    for s in end:
        if isinstance(s, commands.Group):
            end.update(s.commands)
        else:
            end.add(s)

    return end


def get_display_cogs(bot: commands.Bot) -> list[commands.Cog]:
    return [c for c in bot.cogs.values() if not getattr(c, "hidden", False)]


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


async def get_media_info(media: MediaInterface):
    blob = await media.read()
    if isinstance(media, ImageInterface):
        img = Image(blob=blob)
        return MediaInfo(f"image/{img.format}", img.length_of_bytes)
    elif isinstance(media, VideoInterface):
        url = media.url.geturl()
        fmt = url[url.rfind(".") + 1 :]
        return MediaInfo(f"image/{fmt}", len(blob))


def fmt_size(n_bytes: int, cvtn: Convention = Convention.BINARY):
    if cvtn == Convention.BINARY:
        # 2**0  = 0       -> 0 (  B)
        # 2**10 = 1024    -> 1 (KiB)
        # 2**20 = 1048576 -> 2 (MiB)
        # ...
        size_factor = math.log(n_bytes, 2) // 10
    else:
        # 1000**0 = 0       -> 0 ( B)
        # 1000**1 = 1000    -> 1 (KB)
        # 1000**2 = 1000000 -> 2 (MB)
        # ...
        size_factor = math.log(n_bytes, 1000) // 1

    ext: str
    match round(size_factor):  # round only gets rid of the floating `.0`
        case 0:
            ext = "B"
        case 1:
            ext = "KiB"
        case 2:
            ext = "MiB"
        case 3:
            ext = "GiB"
        case 4:
            ext = "TiB"
        case 5:
            ext = "PiB"
        case 6:
            ext = "EiB"
        case 7:
            ext = "ZiB"
        case 8:
            ext = "YiB"
        case _:
            ext = "..."

    if cvtn == Convention.BINARY:
        n_bytes_factored = float(n_bytes) / (2 ** (10 * size_factor))
    else:
        n_bytes_factored = float(n_bytes) / (1000**size_factor)
        ext = ext.replace("i", "")
        ext = ext[:1].lower() + ext[1:]

    nb_fmt = round(n_bytes_factored, 3)
    if nb_fmt // 1 == nb_fmt:
        nb_fmt = int(nb_fmt)

    return f"{nb_fmt} {ext}"


def closest_name(start_hex: str) -> tuple[str, int]:
    start = int(start_hex, 16)
    best: tuple[str, int] | None = None
    for col, (check_hex, _) in COLORS.items():
        if best is None:
            best = col, abs(int(check_hex[1:], 16) - start)

        dif = abs(int(check_hex[1:], 16) - start)

        if dif < best[1]:
            best = col, dif

    return best


async def find_content(
    ctx: VanirContext, msg: discord.Message
) -> MediaInterface | None:
    for atch in msg.attachments:
        mime = atch.content_type
        info = MediaInfo.from_atch(atch)
        if mime.startswith("video/"):
            return await VideoInterface.create(atch, info)
        elif mime.startswith("image/"):
            return await ImageInterface.create(atch, info)
        # else:
        #     raise ValueError(f"Unsupported media type: {mime}")

    uri_regex = re.compile(
        r"https?://([a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    urls = uri_regex.findall(msg.content)
    if urls:
        url = urls[0]  # only test the first URL
        parsed = urlparse(url)
        path = parsed.path
        try:
            extension = path[path.rfind(".") + 1 :].lower()
            if (
                extension
                not in MediaConverter.image_formats + MediaConverter.video_formats
            ):
                raise ValueError

            response = await ctx.bot.session.get(url, allow_redirects=False)
            blob = await response.read()
            info = MediaInfo(f"image/{extension}", blob.__sizeof__())
            if extension in MediaConverter.image_formats:
                info = MediaInfo(f"image/{extension}", blob.__sizeof__())
                return await ImageInterface.from_blob(url, blob, info)
            else:
                info = MediaInfo(f"video/{extension}", blob.__sizeof__())
                return await VideoInterface.from_blob(url, blob, info)
        except ValueError:
            pass

    return None