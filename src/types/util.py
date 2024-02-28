import re
import time
from asyncio import iscoroutinefunction
from dataclasses import dataclass
from urllib.parse import urlparse

import discord
from discord.app_commands import Choice

from src.types.core import VanirContext
from src.types.media import (
    MediaInterface,
    MediaInfo,
    VideoInterface,
    ImageInterface,
    MediaConverter,
)

LANGUAGE_INDEX = {
    "AR": "Arabic",
    "BG": "Bulgarian",
    "CS": "Czech",
    "DA": "Danish",
    "DE": "German",
    "EL": "Greek",
    "EN": "English",
    "ES": "Spanish",
    "ET": "Estonian",
    "FI": "Finnish",
    "FR": "French",
    "HU": "Hungarian",
    "ID": "Indonesian",
    "IT": "Italian",
    "JA": "Japanese",
    "KO": "Korean",
    "LT": "Lithuanian",
    "LV": "Latvian",
    "NB": "Norwegian",
    "NL": "Dutch",
    "PL": "Polish",
    "PT": "Portuguese",
    "RO": "Romanian",
    "RU": "Russian",
    "SK": "Slovak",
    "SL": "Slovenian",
    "SV": "Swedish",
    "TR": "Turkish",
    "UK": "Ukrainian",
    "ZH": "Chinese",
}


@dataclass
class MessageState:
    content: str
    embeds: list[discord.Embed]
    items: list[discord.ui.Item]

    def __str__(self):
        return f"{self.content or '_'} -  {','.join(e.title for e in self.embeds)} - {len(self.items)} children"

    def __repr__(self):
        return self.__str__()


async def timeit(func, *args):
    if iscoroutinefunction(func):
        start = time.time()
        await func(*args)
    else:
        start = time.time()
        func(*args)

    return time.time() - start


async def langcode_autocomplete(itx: discord.Interaction, current: str):
    options = [Choice(name=f"{v} [{k}]", value=k) for k, v in LANGUAGE_INDEX.items()][
        :25
    ]
    options = sorted(
        filter(lambda c: current.lower() in c.name.lower(), options),
        key=lambda c: c.name,
    )
    return options


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
