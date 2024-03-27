from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from src.types.command import VanirCog, uses_sys_assets, vanir_command
from src.types.media import MediaConverter
from src.util.command import assure_working, send_file

if TYPE_CHECKING:
    import discord

    from src.types.core import Vanir, VanirContext


@uses_sys_assets
class Media(VanirCog):
    """Manipulate images and videos."""

    emoji = "\N{FRAME WITH PICTURE}"

    @vanir_command()
    async def rotate(
        self,
        ctx: VanirContext,
        media_atch: discord.Attachment | None = commands.param(
            description="The media to rotate",
            default=None,
            displayed_default="Recently sent media",
        ),
        degrees: commands.Range[int, 0, 360] = commands.param(
            description="How far to rotate (CW). Videos only support multiples of 90",
            default=90,
        ),
    ) -> None:
        """Rotate media."""
        media = await MediaConverter().convert(ctx, media_atch)
        msg = await assure_working(ctx, media)
        await media.rotate(degrees)
        await send_file(self.rotate, msg, media)

    @vanir_command()
    async def flip(
        self,
        ctx: VanirContext,
        media_atch: discord.Attachment | None = commands.param(
            description="The media to flip",
            default=None,
            displayed_default="Recently sent media",
        ),
    ) -> None:
        """Flip media [vertical reflection]."""
        media = await MediaConverter().convert(ctx, media_atch)
        msg = await assure_working(ctx, media)
        await media.flip()
        await send_file(self.flip, msg, media)

    @vanir_command()
    async def flop(
        self,
        ctx: VanirContext,
        media_atch: discord.Attachment | None = commands.param(
            description="The media to flop",
            default=None,
            displayed_default="Recently sent media",
        ),
    ) -> None:
        """Flop media [horizontal reflection]."""
        media = await MediaConverter().convert(ctx, media_atch)
        msg = await assure_working(ctx, media)
        await media.flop()
        await send_file(self.flop, msg, media)

    @vanir_command()
    async def caption(
        self,
        ctx: VanirContext,
        *,
        text: str,
        media_atch: discord.Attachment | None = commands.param(
            description="The media to caption",
            default=None,
            displayed_default="Recently sent media",
        ),
    ) -> None:
        """Add a caption to media."""
        media = await MediaConverter().convert(ctx, media_atch)
        msg = await assure_working(ctx, media)
        await media.caption(text)
        await send_file(self.caption, msg, media)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Media(bot))
