import logging

import discord
from discord.ext import commands

from src.constants import LANGUAGE_NAMES
from src.logging import book
from src.types.command import VanirCog
from src.types.core import TranslatedMessage, VanirContext
from src.types.database import StarBoard as StarBoardDB
from src.util.command import cog_hidden


@cog_hidden
class Events(VanirCog):
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id in (
            (tlink := cached_tlink)["from_channel_id"]
            for cached_tlink in self.bot.cache.tlinks
        ):
            to_channel = self.bot.get_channel(tlink["to_channel_id"])

            from_lang_code = tlink["from_lang_code"]
            to_lang_code = tlink["to_lang_code"]

            json = {
                "text": [message.content[:150]],
                "target_lang": to_lang_code,
            }

            if from_lang_code != "__":
                json["source_lang"] = from_lang_code

            response = await self.bot.session.deepl("/translate", json=json)
            response.raise_for_status()
            tsl = (await response.json())["translations"][0]

            # "detected_source_language" will be what it detected, or what was given, if AUTO
            source = LANGUAGE_NAMES[tsl["detected_source_language"]]
            target = LANGUAGE_NAMES[to_lang_code.upper()]

            if message.channel in self.bot.cache.tlink_translated_messages:
                previous_response_meta = discord.utils.get(
                    self.bot.cache.tlink_translated_messages[message.channel],
                    source_author_id=message.author.id,
                )
                if previous_response_meta is not None:
                    previous_response = await to_channel.fetch_message(
                        previous_response_meta.translated_message_id
                    )
                    previous_embed = previous_response.embeds[0]
                    previous_embed.description += f"\n{tsl['text']}"
                    previous_embed.set_footer(text=f"{source} -> {target}")
                    await previous_response.edit(embed=previous_embed)
                    return

            embed = VanirContext.syn_embed(
                description=f"### [{message.channel.mention}]\n{tsl['text']}",
                user=message.author,
            )
            embed.set_footer(text=f"{source} -> {target}")
            response = await to_channel.send(embed=embed)

            tmes = TranslatedMessage(
                source_message_id=message.id,
                translated_message_id=response.id,
                source_author_id=message.author.id,
            )
            if message.channel in self.bot.cache.tlink_translated_messages:
                self.bot.cache.tlink_translated_messages[message.channel].append(tmes)
            else:
                self.bot.cache.tlink_translated_messages[message.channel] = [tmes]

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        starboard: StarBoardDB = self.bot.db_starboard
        if payload.emoji.name != "\N{WHITE MEDIUM STAR}":
            return

        config = await starboard.get_config(payload.guild_id)

        if config is None:
            return

        channel_id = config["channel_id"]
        threshold = config["threshold"]

        if payload.channel_id == channel_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            await starboard.remove_config(payload.guild_id)

        starboard_channel: discord.TextChannel = guild.get_channel(channel_id)
        if starboard_channel is None:
            await starboard.remove_config(payload.guild_id)
            return

        n_stars: int = await starboard.add_star(
            payload.guild_id, payload.message_id, payload.user_id
        )

        # starred message channel
        original_channel = guild.get_channel(payload.channel_id)
        if original_channel is None:
            return

        # find if there is already an existing starboard post for the message
        data = await starboard.get_post_data(payload.message_id)
        existing_post_id = data["starboard_post_id"]

        if existing_post_id is None:
            if n_stars >= threshold:
                # get channel to send post to, from cache

                # create embed
                author = guild.get_member(payload.user_id)
                if author is None:
                    book.warning(
                        f"cannot find starboard user in cache",
                        user=payload.user_id,
                    )

                # get message content
                try:
                    message = await original_channel.fetch_message(payload.message_id)
                except discord.NotFound:
                    raise RuntimeError("Could not find content of reacted message")
                real_stars = discord.utils.find(
                    lambda r: r.emoji == "\N{WHITE MEDIUM STAR}", message.reactions
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
                await starboard.set_starboard_post(
                    payload.message_id,
                    message.id,
                    payload.guild_id,
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
        if payload.emoji.name is None or payload.emoji.name != "\N{WHITE MEDIUM STAR}":
            return

        config = await starboard.get_config(payload.guild_id)
        if config is None:
            return

        starboard_channel_id = config["channel_id"]
        threshold = config["threshold"]

        if payload.channel_id == starboard_channel_id:
            return

        n_stars = await starboard.remove_star(
            payload.guild_id, payload.message_id, payload.user_id
        )

        data = await starboard.get_post_data(payload.message_id)
        if data is None:
            return

        existing_post_id = data["starboard_post_id"]
        posting_channel = self.bot.get_channel(starboard_channel_id)

        try:
            existing_post = await posting_channel.fetch_message(existing_post_id)
        except discord.NotFound:
            # starboard post deleted
            await starboard.remove_starboard_post(existing_post_id)
            return

        if n_stars < threshold:
            await existing_post.delete()
            await starboard.remove_starboard_post(existing_post_id)

        else:
            await existing_post.edit(content=f":star: {n_stars}")


async def setup(bot):
    await bot.add_cog(Events(bot))
