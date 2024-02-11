import logging

import discord
from discord.ext import commands

from src.types.command_types import VanirCog
from src.types.core_types import Vanir
from src.types.db_types import StarBoard as StarBoardDB


class StarBoard(VanirCog):
    def __init__(self, bot: Vanir):
        super().__init__(bot)
        # add event listener

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        starboard: StarBoardDB = self.bot.db_starboard

        if payload.emoji.name != "star":
            return
        starboard_channel_id = await starboard.get_starboard_channel(payload.guild_id)
        if starboard_channel_id is None:
            return

        guild = self.bot.get_guild(payload.guild_id)

        starboard_channel: discord.TextChannel = guild.get_channel(starboard_channel_id)

        n_stars: int = await starboard.add_star(payload.guild_id, payload.message_id, payload.user_id)
        # find if there is already an existing starboard post for the message
        existing_post_id: int = await starboard.get_starboard_post_id(payload.message_id)

        # starred message channel
        original_channel = guild.get_channel(payload.channel_id)
        if original_channel is None:
            return

        if existing_post_id is None:
            if n_stars >= await starboard.get_threshold(payload.guild_id):
                # get channel to send post to, from cache

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
                    value=f"(~JUMP LINK~)[https://discordapp.com/channels/{guild.id}/{original_channel.id}/{payload.message_id}]",
                )
                embed.add_field(name="Message ID", value=f"`{payload.message_id}`")
                embed.add_field(name="Channel", value=f"<#{original_channel.id}>", inline=False)
                content = f":star: {n_stars}"

                message = await starboard_channel.send(content=content, embed=embed)
                await starboard.set_starboard_post_id(
                    message.id,
                    payload.guild_id,
                    payload.message_id,
                    payload.user_id,
                    n_stars
                )
            else:  # not enough stars to create a post
                pass  # nothing else to do

        else:  # we need to update the existing post
            existing_post = starboard_channel.get_partial_message(existing_post_id)
            await existing_post.edit(content=f":star: {n_stars}")
