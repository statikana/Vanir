import discord
from discord.ext import commands
from discord.ext.commands import Range

from src.types.command import VanirCog, vanir_group
from src.types.core import Vanir, VanirContext


class StarBoard(VanirCog):
    """Automate a StarBoard channel, featuring popular posts in any channel"""

    emoji = "\N{WHITE MEDIUM STAR}"

    @vanir_group(aliases=["sb"])
    async def starboard(
        self,
        ctx: VanirContext,
        channel: discord.TextChannel | None = commands.param(
            description="The channel to send starboard posts to",
            default=None,
        ),
        threshold: Range[int, 1] = commands.param(
            description="The amount of :star: reactions a message needs to have before being sent to the channel",
            default=1,
        ),
    ):
        """Feature hot posts! [default: `\\starboard get` or `\\starboard setup ...`]"""
        if channel is not None:
            await ctx.invoke(self.setup, channel=channel, threshold=threshold)
        else:
            await ctx.invoke(self.get)

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

        await self.bot.db_starboard.set_config(ctx.guild.id, channel.id, threshold)
        embed = ctx.embed(
            title="Starboard Set Up!",
        )
        embed.add_field(name="Channel", value=f"<#{channel.id}>")
        embed.add_field(name="Star Post Threshold", value=threshold)
        await ctx.reply(embed=embed)

    @starboard.command()
    async def remove(self, ctx: VanirContext):
        """Removes the starboard configuration for your server"""
        await self.bot.db_starboard.remove_config(ctx.guild.id)
        embed = ctx.embed(
            title="Starboard Removed", description="Starboard successfully removed."
        )
        await ctx.reply(embed=embed)

    @starboard.command()
    async def get(self, ctx: VanirContext):
        """Gets the starboard configuration for your server"""
        config = await self.bot.db_starboard.get_config(ctx.guild.id)
        if config is None:
            embed = ctx.embed(
                title="Starboard Configuration",
                description="No starboard configuration found. Use `\\starboard setup` to set one up!",
            )
            await ctx.reply(embed=embed)
            return

        channel = ctx.guild.get_channel(config["channel_id"])
        embed = ctx.embed(
            title="Starboard Configuration",
        )
        embed.add_field(name="Channel", value=channel.mention)
        embed.add_field(name="Star Post Threshold", value=config["threshold"])
        await ctx.reply(embed=embed)


async def setup(bot: Vanir):
    await bot.add_cog(StarBoard(bot))
