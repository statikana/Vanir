from __future__ import annotations

import re
import time
import unicodedata
from asyncio import iscoroutinefunction
from typing import TYPE_CHECKING, Any, Callable

import discord
import pint
import texttable
from discord.ext import commands
from pint import UnitRegistry

from src.constants import (
    ALL_PERMISSIONS,
    GLOBAL_CHANNEL_PERMISSIONS,
    STRONG_CHANNEL_PERMISSIONS,
    TEXT_CHANNEL_PERMISSIONS,
    TIMESTAMP_STYLES,
    VALID_IMAGE_FORMATS,
    VOICE_CHANNEL_PERMISSIONS,
)
from src.types.command import VanirCog, vanir_command
from src.util.format import ctext, format_bool, format_dict
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
from src.util.time import ShortTime, regress_time

if TYPE_CHECKING:
    from src.types.core import Vanir, VanirContext

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
            # check cache first

        sf = int(snowflake)

        found: bool = False
        if search:
            cache_attributes = ("user", "channel", "guild", "role", "emoji")

            fetch_attributes = ("message", "user", "channel", "role")

            for cache_attr in cache_attributes:
                if await self.scan_methods(ctx, "get", cache_attr, sf):
                    found = True
                    break
            else:
                for fetch_attr in fetch_attributes:
                    if await self.scan_methods(ctx, "fetch", fetch_attr, sf):
                        found = True
                        break
        else:
            self.snowflake.reset_cooldown(ctx)

        if not found:
            embed = await self.snowflake_info_embed(ctx, sf)
            await ctx.reply(embed=embed)

    @vanir_command(aliases=["ci", "char", "chars"])
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
            value=f"{"in " if ts > time.time() else ""}{regress_time(ts)}{" ago" if ts < time.time() else ""}",
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

    async def scan_methods(
        self,
        ctx: VanirContext,
        method: str,
        attr: str,
        snowflake: int,
    ) -> bool:
        if attr == "message":
            received = discord.utils.find(
                lambda m: m.id == snowflake,
                ctx.bot.cached_messages,
            )
            if received is None:
                try:
                    received = await ctx.channel.fetch_message(snowflake)
                except discord.NotFound:
                    return False
        else:
            sources = (self.bot, ctx.guild, ctx.channel)
            received: Any = None
            for source in sources:
                try:
                    func = getattr(source, f"{method}_{attr}")
                    received = await self.maybecoro_get(func, snowflake)
                except (AttributeError, discord.NotFound):
                    continue

        if received is None:
            return False

        embed: discord.File = await getattr(self, f"{attr}_info_embed")(ctx, received)
        
        if "ansi" in embed.description:
            file = discord.File("assets/spacer.png")
            embed.set_image(url="attachment://spacer.png")
        else:
            file = None
            
        await ctx.reply(embed=embed, file=file)
        return True

    async def maybecoro_get(self, method: Callable[[int], Any], snowflake: int) -> Any:
        if iscoroutinefunction(method):
            received = await method(snowflake)
        else:
            received = method(snowflake)
        return received

    async def user_info_embed(
        self,
        ctx: VanirContext,
        user: discord.User,
    ) -> discord.Embed:
        member = ctx.guild.get_member_named(user.name)

        embed = ctx.embed(title=f"User: {user.name}", description=f"ID: `{user.id}`")
        created_ts = int(user.created_at.timestamp())
        embed.add_field(
            name="Created At",
            value=f"<t:{created_ts}:F> [<t:{created_ts}:R>]",
            inline=False,
        )
        embed.add_field(
            name=f"Mutual Guilds [`{len(user.mutual_guilds)}`]",
            value="\n".join(
                f"- {guild.name} [ID: `{guild.id}`]" for guild in user.mutual_guilds[:7]
            ),
            inline=False,
        )
        data = {
            "Bot?": user.bot,
            "System?": user.system,
        }

        if member is not None:
            data.update({"Color": closest_color_name(str(member.color)[1:])[0].title()})

        embed.add_field(name="Misc. Data", value=format_dict(data), inline=False)

        if member is not None:
            embed.add_field(
                name="Roles",
                value=f"{(len(member.roles) - 1):,} Total\nTop: {' '.join(r.mention for r in sorted(filter(lambda r: r.name != '@everyone', member.roles), key=lambda r: r.permissions.value, reverse=True)[:3])}",
            )
        # discord.Permissions.value
        await self.add_sf_data(embed, user.id)

        embed.set_image(url=(member or user).display_avatar.url)

        return embed

    async def channel_info_embed(
        self,
        ctx: VanirContext,
        channel: discord.abc.GuildChannel,
    ) -> discord.Embed:
        embed = ctx.embed(
            title=f"{str(channel.type).replace('_', ' ').title()} Channel: {channel.name}",
            description=f"ID: `{channel.id}`\nGuild: {channel.guild} [ID: `{channel.guild.id}`]",
        )

        if channel.category is not None:
            cat = channel.category
            data = {
                "Name": cat.name,
                "ID": f"`{cat.id}`",
                "Created At": f"<t:{int(cat.created_at.timestamp())}:R>",
                "NSFW?": cat.is_nsfw(),
            }
            embed.add_field(name="Category Data", value=format_dict(data))

        await self.add_permission_data_from_channel(ctx, embed, channel)

        embed.add_field(name="Jump URL", value=f"[[JUMP]]({channel.jump_url})")

        await self.add_sf_data(embed, channel.id)
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
        permissions: dict[str, discord.Permissions],
        *,
        checked: list[str],
    ) -> str:
        table = texttable.Texttable(max_width=0)

        table.header(["permission", *list(permissions)])
        table.set_header_align(["r"] + (["l"] * (len(permissions))))
        table.set_cols_align(["r"] + (["l"] * (len(permissions))))
        table.set_cols_dtype(["t"] + (["b"] * (len(permissions))))

        table.set_deco(
            texttable.Texttable.HEADER
            | texttable.Texttable.VLINES,
        )

        for name in checked:
            table.add_row(
                [
                    name.replace("_", " ").title(),
                    *(getattr(p, name) for p in permissions.values()),
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
        print(drawn)
        return f"**```ansi\n{drawn}```**"

    async def add_permission_data_from_channel(
        self,
        ctx: VanirContext,
        embed: discord.Embed,
        channel: discord.abc.GuildChannel,
    ) -> None:
        default = channel.permissions_for(ctx.guild.default_role)
        you = channel.permissions_for(ctx.author)
        me = channel.permissions_for(ctx.me)

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
        embed.description += "\n" + data

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


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Info(bot))
