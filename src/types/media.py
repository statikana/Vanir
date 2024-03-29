from __future__ import annotations

import asyncio
import io
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar
from urllib.parse import urlparse

import cv2
import discord
from discord.ext import commands
from wand.image import Image

from src.constants import MONOSPACE_FONT_HEIGHT_RATIO
from src.logging import book
from src.util.regex import URL_REGEX

if TYPE_CHECKING:
    from src.types.core import VanirContext

MediaSource = TypeVar("MediaSource", cv2.Mat, Image)


@dataclass
class MediaInfo:
    mime_type: str
    size: int

    @classmethod
    def from_atch(cls, atch: discord.Attachment):
        return cls(atch.content_type, atch.size)


class MediaInterface(Generic[MediaSource]):
    initial_info: MediaInfo

    @classmethod
    async def create(cls, source: bytes) -> MediaInterface: ...

    @classmethod
    async def from_blob(cls, url: str, blob: bytes) -> None: ...

    async def rotate(self, degrees: int) -> None: ...

    async def flip(self) -> None: ...

    async def flop(self) -> None: ...

    async def read(self) -> bytes: ...

    async def to_file(self) -> discord.File: ...

    async def caption(self, text: str) -> bytes: ...


class ImageInterface(MediaInterface[Image]):
    def __init__(self, image: Image, initial_info: MediaInfo) -> None:
        self.image = image
        self.initial_info = initial_info
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def create(
        cls,
        source: discord.Attachment,
        initial_info: MediaInfo,
    ) -> ImageInterface:
        check_media_size(source)
        return cls(Image(blob=await source.read()), initial_info)

    @classmethod
    async def from_blob(
        cls,
        url: str,
        blob: bytes,
        initial_info: MediaInfo,
    ) -> ImageInterface:
        return cls(Image(blob=blob), initial_info)

    async def rotate(self, degrees: int) -> bytes:
        await self.loop.run_in_executor(None, self.image.rotate, degrees)
        return await self.read()

    async def flip(self) -> bytes:
        await self.loop.run_in_executor(None, self.image.flip)
        return await self.read()

    async def flop(self) -> bytes:
        await self.loop.run_in_executor(None, self.image.flop)
        return await self.read()

    async def read(self) -> bytes:
        return await self.loop.run_in_executor(None, self.image.make_blob, "png")

    async def to_file(self) -> discord.File:
        return discord.File(io.BytesIO(await self.read()), filename="media.png")


class VideoInterface(MediaInterface[cv2.Mat]):
    def __init__(self, url: str, blob: bytes, initial_info: MediaInfo) -> None:
        self.url = urlparse(url)
        self.blob = blob
        self.initial_info = initial_info
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def create(
        cls,
        source: discord.Attachment,
        initial_info: MediaInfo,
    ) -> VideoInterface:
        check_media_size(source)
        return cls(source.url, await source.read(), initial_info)

    @classmethod
    async def from_blob(cls, url: str, blob: bytes, info: MediaInfo) -> VideoInterface:
        return cls(url, blob, info)

    async def rotate(self, degrees: int) -> bytes:
        if degrees % 90 != 0:
            msg = "Degrees must be a multiple of 90"
            raise ValueError(msg)
        n_rots = degrees // 90 % 4

        match n_rots:
            case 0:
                params = ""  # 0 deg
            case 1:
                params = '-vf "transpose=1"'  # 90 CW
            case 2:
                params = '-vf "vflip" -vf "hflip"'
            case 3:
                params = '-vf "transpose=2"'  # 90 CCW
            case _:
                raise RuntimeError(degrees, n_rots)

        self.blob = await self.send_proc_pipe(params)
        return self.blob

    async def caption(self, text: str) -> bytes:
        book.info("Here")
        # https://stackoverflow.com/questions/17623676/text-on-video-ffmpeg
        # https://stackoverflow.com/questions/46671252/how-to-add-black-borders-to-video
        chars_per_line = 30
        n_lines = math.ceil(len(text) / chars_per_line)

        font_width = 10
        font_height = MONOSPACE_FONT_HEIGHT_RATIO * font_width

        pix_buff = math.ceil(n_lines * font_height)

        # create a buffer of white pixels to extend the video
        extend_padding_params = (
            f'-filter_complex "[0]pad=h={pix_buff}+ih:color=white:x=0:y=0"'
        )
        self.blob = await self.send_proc_pipe(extend_padding_params)

        text_dict = {
            "text": f"'{text}'",
            "fontfile": "./assets/Monospace.ttf",
            "fontsize": font_height,
            "fontcolor": "black",
        }
        text_params = f"-vf {':'.join(f'{k}={v}' for k, v in text_dict.items())}"
        self.blob = await self.send_proc_pipe(text_params)
        return self.blob

    async def to_file(self) -> discord.File:
        return discord.File(io.BytesIO(self.blob), filename="media.webm")

    async def read(self) -> bytes:
        return self.blob

    async def send_proc_pipe(self, params: str) -> bytes:
        # TODO(statikana): Semaphore for controlling max number of processes open at any one time
        # TODO(statikana): Share processes?
        # https://stackoverflow.com/questions/3937387/rotating-videos-with-ffmpeg

        command = (
            f'ffmpeg -hide_banner -loglevel error -i "{self.url.geturl()}" {params} -f '
            f"matroska pipe:1"
        )
        proc = await asyncio.create_subprocess_shell(
            cmd=command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        rt_code = await proc.wait()
        if rt_code != 0:
            err_msg = (await proc.stderr.read()).decode("utf-8")
            book.warning(err_msg, params=params)
            msg = f"ffmpeg returned non-zero status code. {err_msg}"
            raise ValueError(msg)

        return await proc.stdout.read()


class MediaConverter:
    video_formats = (
        "mp4",
        "webm",
    )
    image_formats = ("jpeg", "jpg", "png", "gif")

    async def convert(
        self,
        ctx: VanirContext,
        atch: discord.Attachment | None,
    ) -> MediaInterface:
        data = await find_content(ctx, ctx.message)
        if data is not None:
            return data

        if ctx.message.reference is not None:
            reference = await ctx.channel.fetch_message(
                ctx.message.reference.message_id,
            )
            return await find_content(ctx, reference)

        async for h_msg in ctx.channel.history(limit=8):
            data = await find_content(ctx, h_msg)
            if data is not None:
                return data

        msg = "Could not locate any image information"
        raise ValueError(msg)


def check_media_size(obj: discord.Attachment | bytes | None) -> None:
    if obj is not None:
        if (isinstance(obj, discord.Attachment) and obj.size > (10**7)) or (
            isinstance(obj, bytes) and len(obj) > (10**7)
        ):
            raise commands.CommandInvokeError(
                ValueError("Attachment size cannot be more than 10 mB"),
            )


async def find_content(
    ctx: VanirContext,
    msg: discord.Message,
) -> MediaInterface | None:
    for atch in msg.attachments:
        mime = atch.content_type
        info = MediaInfo.from_atch(atch)

        if mime.startswith("video/"):
            return await VideoInterface.create(atch, info)

        elif mime.startswith("image/"):
            return await ImageInterface.create(atch, info)

    urls = URL_REGEX.findall(msg.content)
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
                msg = "Invalid extension"
                raise ValueError(msg)

            response = await ctx.bot.session.get(url, allow_redirects=False)
            blob = await response.read()
            check_media_size(blob)
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
