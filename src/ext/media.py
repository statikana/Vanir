import discord
from discord.ext import commands

from src.types.command import VanirCog, vanir_command
from src.types.core import VanirContext, Vanir
from src.types.media import MediaConverter


class Media(VanirCog):
    @vanir_command()
    async def rot(
        self,
        ctx: VanirContext,
        media_file: discord.Attachment | None = commands.param(
            description="The media to rotate",
            default=None,
            displayed_default="Recently sent media",
        ),
        degrees: commands.Range[int, 0, 360] = commands.param(
            description="How far to rotate (CW). Videos only support multiples of 90",
            default=45,
        ),
    ):
        """Rotate media"""
        media = await MediaConverter().convert(ctx, media_file)
        await media.rotate(degrees)
        await ctx.reply(file=await media.to_file())

    @vanir_command()
    async def flip(
        self,
        ctx: VanirContext,
        media_file: discord.Attachment | None = commands.param(
            description="The media to flip",
            default=None,
            displayed_default="Recently sent media",
        ),
    ):
        """Flip media on the x-axis"""
        media = await MediaConverter().convert(ctx, media_file)
        await media.flip()
        await ctx.reply(file=await media.to_file())

    @vanir_command()
    async def flop(
        self,
        ctx: VanirContext,
        media_file: discord.Attachment | None = commands.param(
            description="The media to flop",
            default=None,
            displayed_default="Recently sent media",
        ),
    ):
        """Flop media on the y-axis"""
        media = await MediaConverter().convert(ctx, media_file)
        await media.flop()
        await ctx.reply(file=await media.to_file())


async def setup(bot: Vanir):
    await bot.add_cog(Media(bot))
