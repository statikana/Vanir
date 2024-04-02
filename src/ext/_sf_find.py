# methods which search discord for a certain object
# methods for cache and making a api call
# all methods take VanirContext and the snowflake ID of the object to search for
# and a bool of whether to make an API call if not in cache

#    discord.Member,
#     discord.Role,
#     discord.guild.GuildChannel,
#     discord.Emoji,
#     discord.Message,
#     discord.Guild
from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from src.types.core import VanirContext


# MEMBER / USER
async def find_member(
    ctx: VanirContext,
    member_id: int,
    *,
    make_request: bool,
) -> discord.Member | None:
    if member := ctx.guild.get_member(member_id):
        return member
    if member := ctx.bot.get_user(member_id):
        return member

    if make_request:
        try:
            return await ctx.guild.fetch_member(member_id)
        except discord.NotFound:
            pass

        try:
            return await ctx.bot.fetch_user(member_id)
        except discord.NotFound:
            pass

    return None


# ROLE
async def find_role(
    ctx: VanirContext,
    role_id: int,
    *,
    make_request: bool,
) -> discord.Role | None:
    if role := ctx.guild.get_role(role_id):
        return role

    if make_request:
        if role := discord.utils.get(await ctx.guild.fetch_roles(), id=role_id):
            return role

    return None


# CHANNEL
async def find_channel(
    ctx: VanirContext,
    channel_id: int,
    *,
    make_request: bool,
) -> discord.abc.GuildChannel | None:
    if channel := ctx.guild.get_channel(channel_id):
        return channel

    if make_request:
        if channel := discord.utils.get(
            await ctx.guild.fetch_channels(),
            id=channel_id,
        ):
            return channel

    return None


# EMOJI
async def find_emoji(
    ctx: VanirContext,
    emoji_id: int,
    *,
    make_request: bool,
) -> discord.Emoji | None:
    if emoji := ctx.bot.get_emoji(emoji_id):
        return emoji

    if make_request:
        try:
            return await ctx.guild.fetch_emoji(emoji_id)
        except discord.NotFound:
            pass

    return None


# MESSAGE
async def find_message(
    ctx: VanirContext,
    message_id: int,
    *,
    make_request: bool,
) -> discord.Message | None:
    if message := discord.utils.get(ctx.bot.cached_messages, id=message_id):
        return message

    if make_request:
        try:
            return await ctx.channel.fetch_message(message_id)
        except discord.NotFound:
            pass

    return None


# GUILD
async def find_guild(
    ctx: VanirContext,
    guild_id: int,
    *,
    make_request: bool,
) -> discord.Guild | None:
    if guild := ctx.bot.get_guild(guild_id):
        return guild

    if make_request:
        try:
            return await ctx.bot.fetch_guild(guild_id)
        except discord.NotFound:
            pass

    return None
