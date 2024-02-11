import logging

import discord
from discord.ext import commands

from src.types.command_types import VanirCog
from src.types.core_types import Vanir


class StarBoard(VanirCog):
    def __init__(self, bot: Vanir):
        super().__init__(bot)
        # add event listener

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        starboard = self.bot.db_starboard

        if payload.emoji.name != "star":
            return
        starboard_channel = await starboard.get_starboard_channel(payload.guild_id)
        if starboard_channel is None:
            return

        guild = self.bot.get_guild(payload.guild_id)

        await starboard.add_star(payload.message_id)
        # find if there is already an existing starboard post for the message
        existing_post: discord.Message = await starboard.get_post(payload.message_id)
        stars: int = await starboard.get_stars(payload.message_id)

        if existing_post is None:
            if stars >= await starboard.get_threshold(payload.guild_id):
                # get channel to send post to, from cache
                channel = guild.get_channel(payload.channel_id)
                if channel is None:
                    return

                # create embed
                author = guild.get_member(payload.user_id)
                if author is None:
                    logging.warning(
                        f"cannot find starboard user in cache {payload.user_id}"
                    )
                embed = discord.Embed(color=discord.Color.gold())
                embed.set_author(
                    name=f"{author.display_name}", icon_url=author.display_avatar.url
                )
                embed.add_field(
                    name="View Message",
                    value=f"(~JUMP LINK~)[https://discordapp.com/channels/{guild.id}/{channel.id}/{payload.message_id}]",
                )
                embed.add_field(name="Message ID", value=f"`{payload.message_id}`")
                embed.add_field(name="Channel", value=f"<#{channel.id}>", inline=False)
                content = f":star: {stars}"

                await channel.send(content=content, embed=embed)
            else:  # not enough stars to create a post
                pass  # nothing else to do

        else:  # we need to update the existing post
            await existing_post.edit(content=f":star: {stars}")
