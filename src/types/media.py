import asyncio
import io
from typing import TypeVar, Generic

import cv2
import discord
import numpy as np
from discord.ext import commands
from wand.image import Image

MediaSource = TypeVar("MediaSource", cv2.Mat, Image)


class MediaInterface(Generic[MediaSource]):
    @classmethod
    async def create(cls, source: bytes) -> "MediaInterface": ...

    async def rotate(self, degrees: int): ...

    async def flip(self): ...

    async def flop(self): ...

    async def read(self) -> bytes: ...

    async def to_file(self) -> discord.File: ...


class ImageInterface(MediaInterface[Image]):
    def __init__(self, image: Image):
        self.image = image
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def create(cls, source: discord.Attachment):
        return cls(Image(blob=await source.read()))

    async def rotate(self, degrees: int) -> None:
        await self.loop.run_in_executor(None, self.image.rotate, degrees)

    async def flip(self) -> None:
        await self.loop.run_in_executor(None, self.image.flip)

    async def flop(self) -> None:
        await self.loop.run_in_executor(None, self.image.flop)

    async def read(self) -> bytes:
        return await self.loop.run_in_executor(None, self.image.make_blob, "png")

    async def to_file(self) -> discord.File:
        return discord.File(io.BytesIO(await self.read()), filename="media.png")


class VideoInterface(MediaInterface[cv2.Mat]):
    def __init__(self, mat: cv2.Mat):
        self.mat = mat
        self.loop = asyncio.get_running_loop()

    @classmethod
    async def create(cls, source: discord.Attachment):
        blob = await source.read()
        img_array = np.asarray(bytearray(blob), dtype=np.uint8)
        mat = cv2.imdecode(img_array, 0)
        return cls(mat)

    async def rotate(self, degrees: int):
        degrees = (degrees % 360 + 360) % 360
        if degrees % 90 != 0:
            raise ValueError(
                "Videos currently support only rotations of 90-degree intervals"
            )
        mat_c = self.mat.copy()
        for _ in range(degrees // 90):
            mat_c = np.rot90(mat_c)

        return mat_c

    async def flip(self):
        return np.flipud(self.mat)

    async def flop(self):
        return np.fliplr(self.mat)

    async def read(self):
        return await self.loop.run_in_executor(None, self.mat.tobytes)


class MediaConverter:
    async def convert(
        self, ctx: commands.Context, argument: discord.Attachment | None
    ) -> MediaInterface:
        if argument is not None:
            if argument.content_type.startswith("video/"):
                return await VideoInterface.create(argument)
            elif argument.content_type.startswith("image/"):
                return await ImageInterface.create(argument)
            raise TypeError(
                f"Unsupported content_type at {argument.filename}: {argument.content_type}"
            )
        else:
            if ctx.message.reference:
                msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if msg.attachments:
                    return await self.convert(ctx, msg.attachments[0])
            async for message in ctx.history(limit=10):
                if not message.attachments:
                    continue
                for a in message.attachments:
                    try:
                        return await self.convert(ctx, a)
                    except TypeError:
                        continue
            raise ValueError(
                "No attachment, and I could not find any recent attachments to use"
            )
