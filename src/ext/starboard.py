import logging

import discord
from discord.ext import commands
from discord.ext.commands import param, Range

from src.types.command import VanirCog, inherit, vanir_group, vpar
from src.types.core import Vanir, VanirContext
from src.types.database import StarBoard as StarBoardDB


class StarBoard(VanirCog):
    """Automate a StarBoard channel, featuring popular posts in any channel"""

    def __init__(self, bot: Vanir):
        super().__init__(bot)

    @vanir_group()
    async def starboard(self, ctx: VanirContext):
        pass

    @inherit
    @starboard.command()
    async def setup(
        self,
        ctx: VanirContext,
        channel: discord.TextChannel = vpar("The channel to send starboard posts to"),
        threshold: Range[int, 1] = vpar(
            "The amount of :star: reactions a message needs to have before being sent to the channel",
            1,
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

    @inherit
    @starboard.command()
    async def remove(self, ctx: VanirContext):
        """Removes the starboard configuration for your server"""
        await self.bot.db_starboard.remove_data(ctx.guild.id)
        embed = ctx.embed(
            title="Starboard Removed", description="Starboard successfully removed."
        )
        await ctx.reply(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        starboard: StarBoardDB = self.bot.db_starboard
        if payload.emoji.name != "\N{White Medium Star}":
            return

        starboard_channel_id = await starboard.get_starboard_channel(payload.guild_id)
        if payload.channel_id == starboard_channel_id:
            return

        if starboard_channel_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)

        starboard_channel: discord.TextChannel = guild.get_channel(starboard_channel_id)

        n_stars: int = await starboard.add_star(
            payload.guild_id, payload.message_id, payload.user_id
        )

        # find if there is already an existing starboard post for the message

        existing_post_id: int = await starboard.get_starboard_post_id(
            payload.message_id
        )

        # starred message channel
        original_channel = guild.get_channel(payload.channel_id)
        if original_channel is None:
            return

        if existing_post_id is None:
            threshold = await starboard.get_threshold(payload.guild_id)
            if n_stars >= threshold:
                # get channel to send post to, from cache

                # create embed
                author = guild.get_member(payload.user_id)
                if author is None:
                    logging.warning(
                        f"cannot find starboard user in cache {payload.user_id}"
                    )

                # get message content
                try:
                    message = await original_channel.fetch_message(payload.message_id)
                except discord.NotFound:
                    raise RuntimeError("Could not find content of reacted message")
                real_stars = discord.utils.find(
                    lambda r: r.emoji == "\N{White Medium Star}", message.reactions
                )
                if real_stars is None:
                    return  # what?
                n_stars = real_stars.count

                embed = discord.Embed(
                    description=message.content, color=discord.Color.gold()
                )
                embed.set_author(
                    name=f"{message.author.display_name}",
                    icon_url=message.author.display_avatar.url,
                )
                embed.add_field(
                    name="View Message",
                    value=f"[JUMP LINK](https://discordapp.com/channels/{guild.id}/{original_channel.id}/{payload.message_id})",
                )
                embed.add_field(name="Message ID", value=f"`{payload.message_id}`")
                embed.add_field(
                    name="Channel", value=f"<#{original_channel.id}>", inline=False
                )

                if message.attachments:
                    allowed_formats = [".jpg", ".png", ".gif"]
                    image = discord.utils.find(
                        lambda a: any(a.filename.endswith(k) for k in allowed_formats),
                        message.attachments,
                    )
                    if image is not None:
                        embed.set_image(url=image.url)
                content = f":star: {n_stars}"

                message = await starboard_channel.send(content=content, embed=embed)
                await starboard.set_starboard_post_id(
                    message.id,
                    payload.guild_id,
                    payload.message_id,
                    payload.user_id,
                    n_stars,
                )
            else:  # not enough stars to create a post
                pass  # nothing else to do

        else:  # we need to update the existing post
            try:
                existing_post = await starboard_channel.fetch_message(existing_post_id)
                await existing_post.edit(content=f":star: {n_stars}")
            except discord.NotFound:
                await starboard.remove_starboard_post(existing_post_id)
                return
                # this will create a new one next reaction

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        starboard: StarBoardDB = self.bot.db_starboard
        if payload.emoji.name is None or payload.emoji.name != "\N{White Medium Star}":
            return

        starboard_channel_id = await starboard.get_starboard_channel(payload.guild_id)
        if payload.channel_id == starboard_channel_id:
            return

        n_stars = await starboard.remove_star(
            payload.guild_id, payload.message_id, payload.user_id
        )
        threshold = await starboard.get_threshold(payload.guild_id)

        existing_post_id = await starboard.get_starboard_post_id(payload.message_id)
        if existing_post_id is None:
            return

        try:
            existing_post = await self.bot.get_channel(
                starboard_channel_id
            ).fetch_message(existing_post_id)
        except discord.NotFound:
            # starboard post deleted
            await starboard.remove_starboard_post(existing_post_id)
            return

        if n_stars < threshold:

            await existing_post.delete()
            await starboard.remove_starboard_post(existing_post_id)

        else:
            await existing_post.edit(content=f":star: {n_stars}")


async def setup(bot: Vanir):
    await bot.add_cog(StarBoard(bot))
