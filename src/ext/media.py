import discord
from discord.ext import commands

from src.types.command import VanirCog, vanir_command
from src.types.core import VanirContext, Vanir
from src.types.media import MediaConverter, MediaInterface
from src.types.util import find_content
from src.util import assure_working, send_file


class Media(VanirCog):
    @vanir_command()
    async def rot(
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
    ):
        """Rotate media"""

        media = await MediaConverter().convert(ctx, media_atch)
        msg = await assure_working(ctx, media)
        await media.rotate(degrees)
        await send_file(ctx, self.rot, msg, media)


async def setup(bot: Vanir):
    await bot.add_cog(Media(bot))
