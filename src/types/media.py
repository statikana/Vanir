import asyncio
import io
import logging
import re
from dataclasses import dataclass
from typing import TypeVar, Generic

import cv2
import discord
from discord.ext import commands
from wand.image import Image
from urllib.parse import urlparse

from src.types.core import VanirContext
from src.util import find_content

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
    async def create(cls, source: bytes) -> "MediaInterface": ...

    @classmethod
    async def from_blob(cls, url: str, blob: bytes): ...

    async def rotate(self, degrees: int): ...

    async def flip(self): ...

    async def flop(self): ...

    async def read(self) -> bytes: ...

    async def to_file(self) -> discord.File: ...


class ImageInterface(MediaInterface[Image]):

    def __init__(self, image: Image, initial_info: MediaInfo):
        self.image = image
        self.initial_info = initial_info
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def create(
        cls, source: discord.Attachment, initial_info: MediaInfo
    ) -> "ImageInterface":
        return cls(Image(blob=await source.read()), initial_info)

    @classmethod
    async def from_blob(cls, url: str, blob: bytes, initial_info: MediaInfo):
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

    def __init__(self, url: str, blob: bytes, initial_info: MediaInfo):
        self.url = urlparse(url)
        self.blob = blob
        self.initial_info = initial_info
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def create(
        cls, source: discord.Attachment, initial_info: MediaInfo
    ) -> "VideoInterface":
        return cls(source.url, await source.read(), initial_info)

    @classmethod
    async def from_blob(cls, url: str, blob: bytes, info: MediaInfo):
        return cls(url, blob, info)

    async def rotate(self, degrees: int) -> bytes:
        print(degrees)
        if degrees % 90 != 0:
            raise ValueError("Degrees must be a multiple of 90")
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

    async def to_file(self) -> discord.File:
        return discord.File(io.BytesIO(self.blob), filename=f"media.webm")

    async def read(self) -> bytes:
        return self.blob

    async def send_proc_pipe(self, params: str) -> bytes:
        # https://stackoverflow.com/questions/3937387/rotating-videos-with-ffmpeg
        # TODO: Semaphore for controlling max number of processes open at any one time
        # TODO: Share processes?
        print(self.url.geturl())
        command = f'ffmpeg -hide_banner -loglevel error -i "{self.url.geturl()}" -pix_fmt yuv420p -f mp4 -vf "transpose=1" -f matroska pipe:1'
        print(command)
        proc = await asyncio.create_subprocess_shell(
            cmd=command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        rt_code = await proc.wait()

        if rt_code != 0:
            err_msg = (await proc.stderr.read()).decode("utf-8")
            logging.warning(err_msg)
            raise ValueError(f"ffmpeg returned non-zero status code. {err_msg}")

        return await proc.stdout.read()


class MediaConverter:
    video_formats = (
        "mp4",
        "webm",
    )
    image_formats = ("jpeg", "jpg", "png", "gif")

    async def convert(
        self, ctx: VanirContext, atch: discord.Attachment | None
    ) -> MediaInterface:
        data = await find_content(ctx, ctx.message)
        if data is not None:
            return data

        if ctx.message.reference is not None:
            reference = await ctx.channel.fetch_message(
                ctx.message.reference.message_id
            )
            ref_data = await find_content(ctx, reference)
            return ref_data

        async for h_msg in ctx.channel.history(limit=8):
            data = await find_content(ctx, h_msg)
            if data is not None:
                return data

        raise ValueError("Could not locate any image information")
