import discord
from discord.ext import commands
from discord.ext.commands import Range

from src.types.command import VanirCog
from src.util.command import vanir_group
from src.types.core import Vanir, VanirContext


class StarBoard(VanirCog):
    """Automate a StarBoard channel, featuring popular posts in any channel"""

    emoji = "\N{White Medium Star}"

    def __init__(self, bot: Vanir):
        super().__init__(bot)

    @vanir_group()
    async def starboard(self, ctx: VanirContext):
        pass

    @starboard.command()
    async def setup(
        self,
        ctx: VanirContext,
        channel: discord.TextChannel = commands.param(
            description="The channel to send starboard posts to"
        ),
        threshold: Range[int, 1] = commands.param(
            description="The amount of :star: reactions a message needs to have before being sent to the channel",
            default=1,
        ),
    ):
        """Sets up the starboard for your server"""
        if (
            channel.permissions_for(ctx.me).send_messages
            and not ctx.me.guild_permissions.administrator
        ):
            raise ValueError("I'm not allowed to send messages there!")

        await self.bot.db_starboard.set_starboard_channel(
            ctx.guild.id, channel.id, threshold
        )
        embed = ctx.embed(
            title="Starboard Set Up!",
        )
        embed.add_field(name="Channel", value=f"<#{channel.id}>")
        embed.add_field(name="Star Post Threshold", value=threshold)
        await ctx.reply(embed=embed)

    @starboard.command()
    async def remove(self, ctx: VanirContext):
        """Removes the starboard configuration for your server"""
        await self.bot.db_starboard.remove_data(ctx.guild.id)
        embed = ctx.embed(
            title="Starboard Removed", description="Starboard successfully removed."
        )
        await ctx.reply(embed=embed)


async def setup(bot: Vanir):
    await bot.add_cog(StarBoard(bot))
