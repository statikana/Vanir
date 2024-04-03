from __future__ import annotations

import re
import time
import unicodedata
from typing import TYPE_CHECKING, Awaitable

import discord
import pint
import texttable
from discord.ext import commands
from pint import UnitRegistry

from src.constants import (
    ALL_PERMISSIONS,
    EMOJIS,
    GLOBAL_CHANNEL_PERMISSIONS,
    STRONG_CHANNEL_PERMISSIONS,
    TEXT_CHANNEL_PERMISSIONS,
    TIMESTAMP_STYLES,
    VALID_IMAGE_FORMATS,
    VOICE_CHANNEL_PERMISSIONS,
)
from src.ext._sf_find import (
    find_channel,
    find_emoji,
    find_guild,
    find_member,
    find_message,
    find_role,
)
from src.types.command import AcceptItx, VanirCog, VanirView, vanir_command
from src.types.core import SFType, VanirContext
from src.types.interface import EmojiConverter
from src.util.format import ctext, format_bool, format_children, format_dict
from src.util.parse import closest_color_name, find_ext, find_filename, fuzzysearch
from src.util.regex import (
    CONNECTOR_REGEX,
    DISCORD_TIMESTAMP_REGEX,
    EMOJI_REGEX,
    SNOWFLAKE_REGEX,
    SPACE_FORMAT_REGEX,
    SPACE_SUB_REGEX,
    TIMESTAMP_REGEX_REGEX,
    UNIT_SEPARATOR_REGEX,
    UNIT_SEPARATOR_SUB_REGEX,
)
from src.util.time import ShortTime, format_time

if TYPE_CHECKING:
    from src.types.core import Vanir

ureg = UnitRegistry()
units = [
    unit
    for unitname in dir(ureg)
    if isinstance((unit := getattr(ureg, unitname)), pint.Unit)
]
unit_choices = [
    discord.app_commands.Choice(
        name=f"{unit} [{unit.dimensionality.format_babel('P')}]",
        value=str(unit),
    )
    for unit in units
]


class Info(VanirCog):
    """What's this?."""

    emoji = "\N{WHITE QUESTION MARK ORNAMENT}"

    @vanir_command(aliases=["sf", "id"])
    @commands.cooldown(5, 120, commands.BucketType.user)
    async def snowflake(
        self,
        ctx: VanirContext,
        snowflake: str = commands.param(
            description="The snowflake (ID) to get information on",
        ),
        search: bool = commands.param(
            description="Whether or not to search for the object who owns this ID. If this False, there is no cooldown for this command",
            default=True,
        ),
    ) -> None:
        """Gets information on a snowflake (ID). You can access these when using Developer mode in Discord."""
        if not SNOWFLAKE_REGEX.fullmatch(snowflake):
            msg = "Not a snowflake."
            raise ValueError(msg)

        sf = int(snowflake)

        if search:
            methods = [
                find_member,
                find_role,
                find_channel,
                find_emoji,
                find_message,
                find_guild,
            ]
            for finder in methods:
                result = await finder(ctx, sf, make_request=True)
                if result is not None:
                    await self.bot.dispatch_sf(ctx, result)
                    return

        else:
            self.snowflake.reset_cooldown(ctx)

        embed = await self.snowflake_info_embed(ctx, sf)
        await ctx.reply(embed=embed)

    @vanir_command(aliases=["char", "chars"])
    async def charinfo(
        self,
        ctx: VanirContext,
        *,
        chars: str = commands.param(
            description="The characters to evaluate. Gets cut off at 30",
        ),
    ) -> None:
        """Get detailed information about unicode characters."""
        custom_emojis = EMOJI_REGEX.findall(chars)
        if custom_emojis:
            embed = ctx.embed(
                description="\n".join(
                    f"Custom Emoji: `{name}` [ID: `{emoji_id}`, Animated: {'Yes' if a else 'No'}]"
                    for a, name, emoji_id in custom_emojis
                ),
            )
        else:
            codepoints: list[str] = []
            hotlinks: list[str] = []

            for c in chars[:40]:
                full_name = unicodedata.name(c, "<NOT FOUND>")

                codepoint = hex(ord(c))[2:].rjust(4, "0")
                codepoints.append(codepoint)

                info_base = "https://unicodeplus.com/U+"
                info_hot = f"[`{full_name}`]({info_base + codepoint})"

                hotlinks.append(info_hot)

            embed = ctx.embed(
                title=chars,
                description="\n".join(
                    f"`\\U{codepoint}`: {info_hot}"
                    for codepoint, info_hot in zip(codepoints, hotlinks)
                ),
            )

        await ctx.send(embed=embed)

    @vanir_command(aliases=["timestamp", "ts"])
    async def time(
        self,
        ctx: VanirContext,
        *,
        string: str = commands.param(
            description="The time string to convert into a timestamp",
            default="0s",
            displayed_default="now",
        ),
    ) -> None:
        """
        Analyzes a time. Can be relative [1 day -5 seconds] or a timestamp.

        Some of the underlying code is from Rapptz.
        """
        string = re.sub(CONNECTOR_REGEX, "", string.lower())
        if TIMESTAMP_REGEX_REGEX.fullmatch(string) is not None:
            ts = float(string)
        elif (match := DISCORD_TIMESTAMP_REGEX.fullmatch(string)) is not None:
            ts = int(float(match.group("ts")))
        else:
            # remove superfluous spaces (ie 4 minutes 5 hours -> 4minutes 5hours)
            string: str = re.sub(SPACE_FORMAT_REGEX, SPACE_SUB_REGEX, string)

            diff = sum(
                ShortTime(part).dt.timestamp() - time.time() for part in string.split()
            )
            ts = diff + time.time()

        embed = ctx.embed()
        for style, desc in TIMESTAMP_STYLES.items():
            fmt = f"<t:{int(ts)}{f":{style}" if style else ""}>"
            embed.add_field(name=f"{desc}", value=f"{fmt}\n`{fmt}`", inline=True)
        embed.add_field(
            name="DT Delta",
            value=f"{int(ts - time.time())} seconds",
        )
        embed.add_field(name="UNIX Timestamp", value=f"`{ts}`", inline=True)
        embed.add_field(
            name="Human Readable",
            value=f"{"in " if ts > time.time() else ""}{format_time(ts)}{" ago" if ts < time.time() else ""}",
            inline=False,
        )
        await ctx.reply(embed=embed)

    @vanir_command(aliases=["uc", "ucv", "conv", "convert"])
    async def unit(
        self,
        ctx: VanirContext,
        from_: str = commands.param(
            displayed_name="from",
            description="What to convert from (eg 10min, 15kg, 5m/s)",
        ),
        to_unit: str | None = commands.param(
            description="The unit to convert to",
            default=None,
            displayed_default="base unit of (from_unit)",
        ),
    ) -> None:
        """Convert a quantity between compatible units."""
        from_qty, from_unit = UNIT_SEPARATOR_REGEX.sub(
            UNIT_SEPARATOR_SUB_REGEX,
            from_,
        ).split()
        from_pint = ureg(f"{from_qty} {from_unit}")

        if to_unit is None:
            _, to_unit_pint = ureg.get_base_units(from_pint.units)
            if to_unit_pint == from_pint.units:
                # hmm secondary base unit?
                pass
            to_unit = str(to_unit_pint)
            to_pint = ureg(to_unit)
            assumed = True
        else:
            to_pint = ureg(to_unit)
            assumed = False

        if not from_pint.is_compatible_with(to_pint):
            from_fmt = from_pint.dimensionality.format_babel("P")
            to_fmt = to_pint.dimensionality.format_babel("P")
            msg = f"Units `{from_unit}` and `{to_unit}` are not compatible [`{from_fmt}` vs `{to_fmt}`]"
            raise TypeError(
                msg,
            )

        dest = ureg(f"{from_qty} {from_unit}").to(to_unit)

        embed = ctx.embed(
            title=f"{dest.units.default_format} {dest.magnitude}",
        )
        embed.set_footer(
            text=f"{from_qty} {from_unit} -> {dest.units}{" [Assumed Unit]" if assumed else ""}",
        )
        await ctx.reply(embed=embed)

    @unit.autocomplete("to_unit")
    async def unit_autocomplete(
        self,
        itx: discord.Interaction,
        argument: str,
    ) -> list[discord.app_commands.Choice]:
        return fuzzysearch(
            argument,
            unit_choices,
            key=lambda x: x.name,
        )[:25]

    @vanir_command(
        aliases=["user", "member", "who", "userinfo", "ui"],
        sf_receiver=discord.Member,
    )
    async def whois(
        self,
        ctx: VanirContext,
        member: discord.Member = commands.param(
            description="The member to view",
            default=lambda ctx: ctx.author,
            displayed_default="You",
        ),
    ) -> None:
        """Shows information about a member."""
        embed = await self.whois_embed(ctx, member)
        view = VanirView(self.bot, user=ctx.author, accept_itx=AcceptItx.ANY)

        view.add_item(AvatarButton(member, self.whois_avatar_embed))
        view.add_item(PermissionsButton(member, self.whois_permissions))

        await ctx.send(embed=embed, view=view)

    @vanir_command(aliases=["mi"], sf_receiver=discord.Message)
    async def messageinfo(
        self,
        ctx: VanirContext,
        message: discord.Message = commands.param(
            description="The message to view",
            default=lambda ctx: ctx.message,
            displayed_default="This message",
        ),
    ) -> None:
        """Shows information about a message."""
        embed = await self.message_info_embed(ctx, message)
        await ctx.send(embed=embed)

    @vanir_command(aliases=["gi"], sf_receiver=discord.Guild)
    async def guildinfo(
        self,
        ctx: VanirContext,
        guild: discord.Guild = commands.param(
            description="The guild to view",
            default=lambda ctx: ctx.guild,
            displayed_default="This guild",
        ),
    ) -> None:
        """Shows information about a guild."""
        embed = await self.guild_info_embed(ctx, guild)
        await ctx.send(embed=embed)

    @vanir_command(aliases=["ri"], sf_receiver=discord.Role)
    async def roleinfo(
        self,
        ctx: VanirContext,
        role: discord.Role = commands.param(
            description="The role to view",
        ),
    ) -> None:
        """Shows information about a role."""
        embed = await self.role_info_embed(ctx, role)
        await ctx.send(embed=embed)

    @vanir_command(aliases=["ei"], sf_receiver=discord.Emoji)
    async def emojiinfo(
        self,
        ctx: VanirContext,
        emoji: discord.Emoji = commands.param(
            description="The emoji to view",
            converter=EmojiConverter(),
        ),
    ) -> None:
        """Shows information about an emoji."""
        embed = await self.emoji_info_embed(ctx, emoji)
        await ctx.send(embed=embed)

    @vanir_command(aliases=["ci"], sf_receiver=discord.abc.GuildChannel)
    async def channelinfo(
        self,
        ctx: VanirContext,
        channel: discord.abc.GuildChannel = commands.param(
            description="The channel to view",
            default=lambda ctx: ctx.channel,
            displayed_default="This channel",
        ),
    ) -> None:
        """Shows information about a channel."""
        embed = await self.channel_info_embed(ctx, channel)

        view = VanirView(self.bot, user=ctx.author)
        view.add_item(PermissionsButton(channel, self.channelinfo_permissions))

        revoke_invites = RemoveInvitesButton(channel)
        revoke_invites.disabled = not (
            channel.permissions_for(ctx.author).manage_channels
            or ctx.author.guild_permissions.manage_guild
            or ctx.author.guild_permissions.administrator
        )
        view.add_item(revoke_invites)

        await ctx.send(embed=embed, view=view)

    async def whois_embed(self, ctx: VanirContext, member: discord.Member) -> None:
        embed = ctx.embed(
            title=member.name,
            color=member.color,
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        name, value = format_whois_identity(member)
        embed.add_field(
            name=name,
            value=value,
        )

        name, value = format_whois_times(member)
        embed.add_field(
            name=name,
            value=value,
        )

        embed.add_field(
            name="ㅤ",
            value="ㅤ",
        )

        name, value = format_whois_badges(member)
        embed.add_field(
            name=name,
            value=value,
        )

        name, value = format_whois_roles(member)
        embed.add_field(
            name=name,
            value=value,
        )

        embed.add_field(
            name="ㅤ",
            value="ㅤ",
        )

        name, value = format_whois_statues(member)
        embed.add_field(
            name=name,
            value=value,
        )

        name, value = format_whois_boosting(member)
        embed.add_field(
            name=name,
            value=value,
        )

        embed.add_field(
            name="ㅤ",
            value="ㅤ",
        )
        return embed

    async def whois_avatar_embed(
        self,
        itx: discord.Interaction,
        member: discord.Member,
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=member.name,
            color=member.color,
            user=itx.user,
        )
        embed.set_image(url=member.display_avatar.url)
        await itx.response.send_message(embed=embed, ephemeral=True)

    async def whois_permissions(
        self,
        itx: discord.Interaction,
        member: discord.Member,
    ) -> discord.Embed:
        content = await self.get_permission_table(
            {"?": member.resolved_permissions or member.guild_permissions},
            checked=ALL_PERMISSIONS,
            hlines=False,
        )
        embed = VanirContext.syn_embed(
            title="Permissions",
            description=content,
            user=itx.user,
        )
        embed.set_image(url="attachment://spacer.png")
        file = discord.File("assets/spacer.png")
        await itx.response.send_message(embed=embed, file=file, ephemeral=True)

    async def channelinfo_permissions(
        self,
        itx: discord.Interaction,
        channel: discord.abc.GuildChannel,
    ) -> discord.Embed:
        content = await self.get_permission_data_from_channel(
            itx,
            channel,
        )
        embed = VanirContext.syn_embed(
            title="Channel Permissions",
            description=content,
            user=itx.user,
        )
        embed.set_image(url="attachment://spacer.png")
        file = discord.File("assets/spacer.png")
        await itx.response.send_message(embed=embed, file=file, ephemeral=True)

    async def channel_info_embed(
        self,
        ctx: VanirContext,
        channel: discord.abc.GuildChannel,
    ) -> discord.Embed:
        formatted_type = (channel.type.name.replace("_", " ") + " Channel").title()
        embed = ctx.embed(
            title=f"`{formatted_type}`: {channel.name}",
        )

        name, value = format_channel_meta(channel)  # name, id, topic
        embed.add_field(
            name=name,
            value=value,
        )

        name, value = format_channel_settings(channel)  # slowmode, nsfw, thread timeout

        embed.add_field(
            name=name,
            value=value,
        )

        # spacer
        embed.add_field(
            name="ㅤ",
            value="ㅤ",
        )

        name, value = await format_channel_invites(channel)  # invites
        embed.add_field(
            name=name,
            value=value,
        )

        return embed

    async def message_info_embed(
        self,
        ctx: VanirContext,
        msg: discord.Message,
    ) -> discord.Embed:
        embed = ctx.embed(
            title=f"Message in `#{msg.channel.name}` by `{ctx.author.name}`",
            description=f"{msg.content}",
        )

        if msg.reference is not None:
            ref = await msg.channel.fetch_message(msg.reference.message_id)
            if ref is not None:
                if ref.content:
                    embed.add_field(
                        name="Replying To",
                        value=f"***`{ref.author.name}`***:\n>>> {discord.utils.escape_markdown(ref.content[:100])}",
                    )

        if msg.content:
            mentions = {}

            if msg.mentions:
                mentions.update({"Users": " ".join(o.mention for o in msg.mentions)})
            if msg.role_mentions:
                mentions.update(
                    {"Roles": " ".join(o.mention for o in msg.role_mentions)},
                )
            if msg.channel_mentions:
                mentions.update(
                    {"Channels": " ".join(o.mention for o in msg.channel_mentions)},
                )

            if mentions:
                embed.add_field(name="Mentions", value=format_dict(mentions))

            pat = r"\s"
            content_info = {
                "Length": f"{len(msg.content):,}",
                "# Chars": f"{len(re.sub(pat, '', msg.content)):,}",
                "# Words": f"{len(msg.content.split()):,}",
                "# Lines": f"{len(msg.content.splitlines()):,}",
            }

            embed.add_field(name="Content Info", value=format_dict(content_info))

        if msg.attachments:
            urls = [a.url.lower() for a in msg.attachments]
            file_names = []
            for url in urls:
                file_names.append(find_filename(url))
                extension = find_ext(url)

                if embed.image is None and extension in VALID_IMAGE_FORMATS:
                    embed.set_image(url=url)

            embed.add_field(
                name="Attachments",
                value=" ".join(
                    f"[{name}]({url})" for name, url in zip(file_names, urls)
                ),
            )

        embed.set_footer(text=msg.author.name, icon_url=msg.author.display_avatar.url)
        return embed

    async def guild_info_embed(
        self,
        ctx: VanirContext,
        guild: discord.Guild,
    ) -> discord.Embed:
        embed = ctx.embed(
            title=f"Guild: {guild.name}",
        )
        member_data = {
            "Members": guild.member_count or guild.approximate_member_count,
            "Bots": len(set(filter(lambda m: m.bot, guild.members))),
            "Max Members": f"{guild.max_members:,}",
        }
        embed.add_field(name="Member Info", value=format_dict(member_data))

        boost_data = {
            "Boost Count": f"{guild.premium_subscription_count:,}",
            "Recent Boosters": " ".join(
                b.name
                for b in sorted(
                    guild.premium_subscribers,
                    key=lambda m: m.premium_since,
                )[:5]
            ),
            "Booster Role": (
                guild.premium_subscriber_role.mention
                if guild.premium_subscriber_role
                else None
            ),
            "Boost Level": f"{guild.premium_tier} / 3",
        }
        embed.add_field(name="Boost Info", value=format_dict(boost_data))
        await self.add_sf_data(embed, guild.id)
        return embed

    async def role_info_embed(
        self,
        ctx: VanirContext,
        role: discord.Role,
    ) -> discord.Embed:
        embed = ctx.embed(f"Role: {role.name}")

        embed.description = await self.get_permission_table(
            {f"'{role.name[:20]}'": role.permissions},
            checked=ALL_PERMISSIONS,
        )

        embed.add_field(
            name="Role Info",
            value=format_dict(
                {
                    "\N{ARTIST PALETTE}Color": closest_color_name(str(role.color)[1:])[
                        0
                    ].title(),
                    "\N{SPEECH BALLOON}Mentionable?": f"`{role.mentionable}`",
                    "\N{UP-POINTING RED TRIANGLE}Hoisted?": f"`{role.hoist}`",
                    "\N{TWISTED RIGHTWARDS ARROWS}Position": f"`{role.position}`",
                    "\N{ROBOT FACE}Managed by Bot?": f"`{role.is_bot_managed() or role.is_integration()}`",
                    "\N{HEAVY BLACK HEART}\N{ZERO WIDTH JOINER}\N{FIRE}Nitro Role?": f"`{role.is_premium_subscriber()}`",
                },
            ),
        )
        if role.display_icon:
            if isinstance(role.display_icon, discord.Asset):
                url = role.display_icon.url
            else:
                url = role.display_icon
            embed.set_thumbnail(url=url)

        return embed

    async def emoji_info_embed(
        self,
        ctx: VanirContext,
        emoji: discord.Emoji | discord.PartialEmoji,
    ) -> discord.Embed:
        if isinstance(emoji, discord.PartialEmoji):
            emoji = await ctx.guild.fetch_emoji(emoji.id)

        embed = ctx.embed(title=f"Emoji: {emoji.name}")
        embed.set_image(url=emoji.url)

        embed.add_field(name="Created By", value=emoji.user)
        embed.add_field(name="Animated?", value=emoji.animated)
        return embed

    async def get_permission_table(
        self,
        permission_map: dict[str, discord.Permissions],
        *,
        checked: list[str],
        hlines: bool = True,
    ) -> str:
        table = texttable.Texttable(max_width=40)

        table.header(["permission", *list(permission_map)])

        align = ["r"] + ["l"] * len(permission_map)
        dtype = ["t"] + ["b"] * len(permission_map)

        table.set_header_align(align)
        table.set_cols_align(align)
        table.set_cols_dtype(dtype)

        deco = texttable.Texttable.HEADER | texttable.Texttable.VLINES
        if hlines:
            deco |= texttable.Texttable.HLINES
        table.set_deco(deco)

        # if the user has admin, then they have all permissions
        # even though it isn't explicitly listed

        for user, perms in permission_map.items():
            new = discord.Permissions.all() if perms.administrator else perms
            permission_map[user] = new

        for name in checked:
            table.add_row(
                [
                    name.replace("_", " ").title(),
                    *(getattr(p, name) for p in permission_map.values()),
                ],
            )
        drawn = table.draw()
        drawn = drawn.replace("True", f"{format_bool(True)} ").replace(
            "False",
            f"{format_bool(False)}   ",
        )

        for major in (
            check.replace("_", " ").title()
            for check in checked
            if check in STRONG_CHANNEL_PERMISSIONS
        ):
            drawn = drawn.replace(
                major,
                ctext(major, "blue"),
            )
        return f"**```ansi\n{drawn}```**"

    async def get_permission_data_from_channel(
        self,
        itx: discord.Interaction,
        channel: discord.abc.GuildChannel,
    ) -> str:
        default = channel.permissions_for(itx.guild.default_role)
        you = channel.permissions_for(itx.user)
        me = channel.permissions_for(itx.guild.me)

        permission_to_check = list(GLOBAL_CHANNEL_PERMISSIONS)
        if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            permission_to_check.extend(VOICE_CHANNEL_PERMISSIONS)
        if isinstance(channel, discord.TextChannel):
            permission_to_check.extend(TEXT_CHANNEL_PERMISSIONS)

        permission_to_check.sort()

        data = await self.get_permission_table(
            {"you": you, "me": me, "default": default},
            checked=permission_to_check,
        )
        return "\n" + data

    async def snowflake_info_embed(
        self,
        ctx: VanirContext,
        snowflake: int,
    ) -> discord.Embed:
        embed = ctx.embed("No Object Found")
        await self.add_sf_data(embed, snowflake)
        return embed

    async def add_sf_data(self, embed: discord.Embed, snowflake: int) -> None:
        time = int(discord.utils.snowflake_time(snowflake).timestamp())
        as_bin = str(bin(snowflake))

        # lazy way
        generation, process, worker = (
            int(as_bin[:12], 2),
            int(as_bin[12:17], 2),
            int(as_bin[17:22], 2),
        )

        data = {
            "ID": f"`{snowflake}`",
            "Created At": f"<t:{time}:F> [<t:{time}:R>]",
            "Worker ID": f"`{worker}`",
            "Process ID": f"`{process}`",
            "SF Generation ID": f"`{generation}`",
        }

        embed.add_field(name="Snowflake Info", value=format_dict(data), inline=False)


def format_whois_times(member: discord.Member) -> tuple[str, str]:
    join_pos = sorted(member.guild.members, key=lambda m: m.joined_at).index(member) + 1
    children = [
        ("`Created`", f"<t:{round(member.created_at.timestamp())}:R>"),
        ("`Joined`", f"<t:{round(member.joined_at.timestamp())}:R>"),
        ("`Join #`", f"`{join_pos} / {len(member.guild.members)}`"),
    ]
    return format_children(
        title="User ",
        emoji=EMOJIS["join"],
        children=children,
        as_field=True,
    )


def format_whois_badges(member: discord.Member) -> tuple[str, str]:
    flags = [f.name for f in member.public_flags.all()]
    if member.premium_since:
        flags.append("nitro")
    if member.is_timed_out():
        flags.append("timeout")
    if member.bot and not member.public_flags.verified_bot:
        flags.append("bot")

    children = []
    for flag in flags:
        emoji = EMOJIS[f"bdg_{flag}"]
        children.append(
            (
                "",  # no keys
                f"{emoji} `{emoji.description}`",
            ),
        )
    try:
        return format_children(
            title="Badges",
            emoji=EMOJIS["tag"],
            children=children,
            as_field=True,
        )
    except ValueError:
        return (
            f"{EMOJIS['tag']} No Badges",
            "",
        )


def format_whois_identity(member: discord.Member) -> tuple[str, str]:
    children = []
    children.append(
        ("`User`", member.name),
    )
    children.append(
        ("`Name`", member.global_name or member.name),
    )
    if member.nick:
        children.append(
            ("`Nick`", member.nick),
        )
    children.append(
        ("`ID`", f"`{member.id}`"),
    )
    return format_children(
        title="Identity",
        emoji=EMOJIS["info"],
        children=children,
        as_field=True,
    )


def format_whois_roles(member: discord.Member) -> tuple[str, str]:
    top_color_str = closest_color_name(str(member.color))[0]
    children = [
        ("`Amount`", f"`{len(member.roles) - 1}`")
        if len(member.roles) > 1
        else ("`Roles`", f"{EMOJIS["x"]} No roles"),
        (
            "`Top`",
            f"{member.top_role.mention if member.top_role != member.guild.default_role else "@everyone"}",
        ),
        ("`Color`", f"{top_color_str} `[{member.color!s}]`"),
    ]
    if member.top_role.id == member.guild.default_role.id:
        children = children[:1]
    return format_children(
        title="Roles",
        emoji=EMOJIS["role"],
        children=children,
        as_field=True,
    )


def format_whois_statues(member: discord.Member) -> tuple[str, str]:
    device: str = ""
    if member.desktop_status.value != "offline":
        device = "desktop"
    elif member.mobile_status.value != "offline":
        device = "mobile"
    elif member.web_status.value != "offline":
        device = "web"
    else:
        device = "offline"

    device_emoji = EMOJIS[device]
    children = [
        (
            "`Status`",
            f"{EMOJIS[member.status.value]} {member.status.name.replace("_", " ").title()}",
        ),
        ("`Device`", f"{device_emoji} {device.title()}"),
    ]
    activity_type = member.activity.type if member.activity else None
    if activity_type:
        match activity_type:
            case discord.ActivityType.custom:
                activity = f"{member.activity.emoji} {member.activity.name}"
            case discord.ActivityType.playing:
                activity = f"playing {member.activity.name}"
            case discord.ActivityType.streaming:
                activity = f"streaming {member.activity.name}"
            case discord.ActivityType.watching:
                activity = f"watching {member.activity.name}"
            case discord.ActivityType.listening:
                activity = f"listening to {member.activity.name}"
            case discord.ActivityType.competing:
                activity = f"competing in {member.activity.name}"
            case _:
                activity = f"{EMOJIS["x"]}Doing nothing"

    else:
        activity = f"{EMOJIS["x"]}Doing nothing"

    children.append(
        (
            "`Activity`",
            f"\n`  `{activity} {member.activity.details if getattr(member.activity, "details", None) else ""}",
        ),
    )
    return format_children(
        title="Statuses",
        emoji=EMOJIS["status"],
        children=children,
        as_field=True,
    )


def format_whois_boosting(member: discord.Member) -> tuple[str, str]:
    boosting = member.premium_since
    if boosting:
        children = [
            ("`Since`", f"<t:{round(boosting.timestamp())}:R>"),
            ("`Role`", member.guild.premium_subscriber_role.mention),
        ]
    else:
        children = [
            ("", f"{EMOJIS["x"]}Not boosting"),
        ]
    return format_children(
        title="Boosting",
        emoji=EMOJIS["boost"],
        children=children,
        as_field=True,
    )


def format_channel_meta(channel: discord.abc.GuildChannel) -> tuple[str, str]:
    children = [
        ("`Name`", f"`{channel.name}`"),
        ("`ID`", f"`{channel.id}`"),
    ]
    if hasattr(channel, "topic") and channel.topic:
        children.append(
            ("`Topic`", f"{channel.topic}"),
        )
    return format_children(
        title="Meta",
        emoji=EMOJIS["info"],
        children=children,
        as_field=True,
    )


def format_channel_settings(channel: discord.TextChannel) -> tuple[str, str]:
    nsfw = channel.is_nsfw()
    emoji = EMOJIS["check"] if nsfw else EMOJIS["x"]
    children = [
        (
            "`Slowmode`",
            f"`{format_time(channel.slowmode_delay, from_ts=False) if channel.slowmode_delay else 'None'}`",
        ),
        ("`NSFW`", f"{emoji}`{nsfw}`"),
        (
            "`Archive`",
            f"`{format_time(channel.default_auto_archive_duration, from_ts=False)}`",
        ),
    ]
    return format_children(
        title="Settings",
        emoji=EMOJIS["gear"],
        children=children,
        as_field=True,
    )


async def format_channel_invites(channel: discord.TextChannel) -> tuple[str, str]:
    invites = await channel.invites()
    children = []
    if invites:
        invites: list[discord.Invite] = sorted(
            invites,
            key=lambda i: i.created_at,
            reverse=True,
        )[:10]  # type: list[discord.Invite]
        for invite in invites:
            expires = invite.expires_at
            expire_fmt = f"<t:{round(expires.timestamp())}:R>" if expires else "Never"

            author_fmt = invite.inviter.mention if invite.inviter else "[Unknown User]"
            code = invite.id

            fmt = (code, f"{author_fmt} | Expires: {expire_fmt}")
            children.append(fmt)

    else:
        children = [
            ("", f"{EMOJIS["x"]}No invites found"),
        ]
    return format_children(
        title="Invites",
        emoji=EMOJIS["invite"],
        children=children,
        as_field=True,
    )


class AvatarButton(discord.ui.Button):
    def __init__(
        self,
        member: discord.Member,
        method: Awaitable[discord.Embed],
    ) -> None:
        super().__init__(
            label="Avatar",
            style=discord.ButtonStyle.grey,
            emoji=str(EMOJIS["person"]),
        )
        self.member = member
        self.method = method

    async def callback(self, itx: discord.Interaction) -> None:
        await self.method(itx, self.member)


class PermissionsButton(discord.ui.Button):
    def __init__(
        self,
        sf_object: SFType,
        method: Awaitable[discord.Embed],
    ) -> None:
        super().__init__(
            label="Permissions",
            style=discord.ButtonStyle.grey,
            emoji=str(EMOJIS["shield"]),
        )
        self.sf_object = sf_object
        self.method = method

    async def callback(self, itx: discord.Interaction) -> None:
        await self.method(itx, self.sf_object)


class RemoveInvitesButton(discord.ui.Button):
    def __init__(self, channel: discord.abc.GuildChannel) -> None:
        super().__init__(
            label="Revoke Invites",
            style=discord.ButtonStyle.red,
            emoji=str(EMOJIS["x"]),
        )
        self.channel = channel

    async def callback(self, itx: discord.Interaction) -> None:
        invites = await self.channel.invites()
        n_invites = len(invites)
        for invite in await self.channel.invites():
            await invite.delete()

        embed = VanirContext.syn_embed(
            title=f"Revoked {n_invites} Invites",
            user=itx.user,
        )
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Info(bot))
