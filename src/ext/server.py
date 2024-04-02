from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Awaitable

import discord
from discord.ext import commands

from src.constants import ALL_PERMISSIONS, EMOJIS
from src.types.command import (
    AcceptItx,
    AutoTablePager,
    VanirCog,
    VanirContext,
    VanirView,
    vanir_command,
)
from src.util.format import format_children
from src.util.parse import closest_color_name
from src.util.regex import EMOJI_REGEX
from src.util.time import parse_time, regress_time
from src.util.ux import generate_modal

if TYPE_CHECKING:
    from src.types.core import Vanir


class Server(VanirCog):
    """Information about this server."""

    emoji = "\N{HUT}"

    @vanir_command()
    @commands.guild_only()
    async def new(self, ctx: VanirContext) -> None:
        """Shows the list of all new members in the server."""
        members: list[discord.Member] = sorted(
            ctx.guild.members,
            key=lambda m: m.joined_at,
            reverse=True,
        )
        headers = ["name", "joined at"]
        dtypes = ["t", "t"]

        view = AutoTablePager(
            ctx.bot,
            ctx.author,
            headers=headers,
            rows=members,
            row_key=lambda m: [m.name, m.joined_at.strftime("%Y/%m/%d %H:%M:%S")],
            dtypes=dtypes,
            rows_per_page=10,
        )
        permissions = ctx.channel.permissions_for(
            ctx.author,
        ) & ctx.channel.permissions_for(ctx.guild.me)

        timeout = TimeoutButton(ctx, members, view.current)
        timeout.disabled = not permissions.manage_messages
        view.add_item(timeout)

        kick = KickButton(ctx, members, view.current)
        kick.disabled = not permissions.kick_members
        view.add_item(kick)

        ban = BanButton(ctx, members, view.current)
        ban.disabled = not permissions.ban_members
        view.add_item(ban)

        embed = await view.update_embed()
        await view.update(update_content=False)
        view.message = await ctx.reply(embed=embed, view=view)

    @vanir_command(name="emoji", aliases=["steal"])
    async def emoji_(
        self,
        ctx: VanirContext,
        emoji_name: str | None = commands.param(
            description="The name of the added emoji",
            default=None,
            displayed_default="Filename of image",
        ),
        emoji: str | None = commands.param(
            description="The emojis to steal",
            default=None,
        ),
        emoji_image: discord.Attachment | None = commands.param(
            description="The image to use in the emoji",
            default=None,
        ),
    ) -> None:
        """Creates a guild emoji from an image."""
        if emoji is None and emoji_image is None:
            if match := EMOJI_REGEX.fullmatch(emoji_name):
                emoji = emoji_name
                emoji_name = match.group("name")
            else:
                msg = "Please either specify some emojis or an image to display"
                raise ValueError(msg)

        if emoji and emoji_image:
            msg = "Please specify either emojis or an image, not both"
            raise ValueError(msg)

        if emoji:
            if not (match := EMOJI_REGEX.fullmatch(emoji)):
                msg = "Invalid emoji"
                raise ValueError(msg)
            emoji_id = match.group("id")
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
            content = await self.bot.http.get_from_cdn(url)
        else:
            content = await emoji_image.read()

        created = await ctx.guild.create_custom_emoji(
            name=emoji_name,
            image=content,
            reason=f"Emoji creation by {ctx.author.name}",
        )

        embed = ctx.embed(
            title="Emoji Created",
            description=f"{created.name} [ID: `{created.id}`]\n`{created!s}`",
        )
        embed.set_image(url=created.url)
        await ctx.send(embed=embed)

    @vanir_command(aliases=["user", "member", "who", "userinfo", "ui"])
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

    async def whois_embed(self, ctx: VanirContext, member: discord.Member) -> None:
        embed = ctx.embed(
            title=member.name,
            color=member.color,
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        name, value = format_identity(member)
        embed.add_field(
            name=name,
            value=value,
        )

        name, value = format_times(member)
        embed.add_field(
            name=name,
            value=value,
        )

        embed.add_field(
            name="ㅤ",
            value="ㅤ",
        )

        name, value = format_badges(member)
        embed.add_field(
            name=name,
            value=value,
        )

        name, value = format_roles(member)
        embed.add_field(
            name=name,
            value=value,
        )

        embed.add_field(
            name="ㅤ",
            value="ㅤ",
        )

        name, value = format_statues(member)
        embed.add_field(
            name=name,
            value=value,
        )

        name, value = format_boosting(member)
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
        info = self.bot.get_cog("Info")

        content = await info.get_permission_table(
            {"?": member.resolved_permissions or member.guild_permissions},
            checked=ALL_PERMISSIONS,
        )
        embed = VanirContext.syn_embed(
            title="Permissions",
            description=content,
            user=itx.user,
        )
        embed.set_image(url="attachment://spacer.png")
        file = discord.File("assets/spacer.png")
        await itx.response.send_message(embed=embed, file=file, ephemeral=True)


def format_times(member: discord.Member) -> tuple[str, str]:
    join_pos = sorted(member.guild.members, key=lambda m: m.joined_at).index(member) + 1
    children = [
        ("`Created`", f"<t:{round(member.created_at.timestamp())}:R>"),
        ("` Joined`", f"<t:{round(member.joined_at.timestamp())}:R>"),
        ("` Join #`", f"`{join_pos} / {len(member.guild.members)}`"),
    ]
    return format_children(
        title="User ",
        emoji=EMOJIS["join"],
        children=children,
        as_field=True,
    )


def format_badges(member: discord.Member) -> tuple[str, str]:
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
                f"{emoji} {emoji.description}",
            ),
        )

    return format_children(
        title="Badges",
        emoji=EMOJIS["tag"],
        children=children,
        as_field=True,
    )


def format_identity(member: discord.Member) -> tuple[str, str]:
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
        emoji=EMOJIS["bw_info"],
        children=children,
        as_field=True,
    )


def format_roles(member: discord.Member) -> tuple[str, str]:
    top_color_str = closest_color_name(str(member.color))[0]
    children = [
        ("` Amt.`", f"`{len(member.roles) - 1}`"),
        (
            "`  Top`",
            f"{member.top_role.mention if member.top_role != member.guild.default_role else "@everyone"}",
        ),
        ("`Color`", f"{top_color_str} `[{member.color!s}]`"),
    ]
    return format_children(
        title="Roles",
        emoji=EMOJIS["role"],
        children=children,
        as_field=True,
    )


def format_statues(member: discord.Member) -> tuple[str, str]:
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
    return format_children(
        title="Statuses",
        emoji=EMOJIS["status"],
        children=children,
        as_field=True,
    )


def format_boosting(member: discord.Member) -> tuple[str, str]:
    boosting = member.premium_since
    if boosting:
        children = [
            ("`Since`", f"<t:{round(boosting.timestamp())}:R>"),
            ("` Role`", member.guild.premium_subscriber_role.mention),
        ]
    else:
        children = [
            ("", "<Not boosting"),
        ]
    return format_children(
        title="Boosting",
        emoji=EMOJIS["boost"],
        children=children,
        as_field=True,
    )


class NewUsersPager(AutoTablePager):
    def __init__(
        self,
        ctx: VanirContext,
        rows: list[discord.Member],
    ) -> None:
        super().__init__(
            ctx.bot,
            ctx.author,
            headers=["name", "joined at"],
            rows=rows,
            row_key=lambda m: [m.name, m.joined_at.strftime("%Y/%m/%d %H:%M:%S")],
            dtypes=["t", "t"],
            rows_per_page=10,
        )
        self.ctx = ctx

        authp = ctx.author.resolved_permissions
        if authp is None:
            authp = ctx.channel.permissions_for(ctx.author)
        botp = ctx.channel.permissions_for(ctx.guild.me)

        self.timeout.disabled = not (authp.manage_messages and botp.manage_messages)
        self.kick.disabled = not (authp.kick_members and botp.kick_members)
        self.ban.disabled = not (authp.ban_members and botp.ban_members)

    @discord.ui.button(
        label="Timeout...",
        style=discord.ButtonStyle.grey,
        disabled=True,
    )
    async def timeout(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        view = VanirView(self.bot, user=itx.user)
        view.add_item(TimeoutDetachmentSelect(self.ctx, self.rows, self.current))
        await itx.response.send_message(view=view, ephemeral=True)

    @discord.ui.button(
        label="Kick...",
        style=discord.ButtonStyle.red,
        disabled=True,
    )
    async def kick(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        view = VanirView(self.bot, user=itx.user)
        view.add_item(KickDetachmentSelect(self.ctx, self.rows, self.current))
        embed = self.ctx.embed("Kick Users")
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Ban...",
        style=discord.ButtonStyle.red,
        disabled=True,
    )
    async def ban(self, itx: discord.Interaction, button: discord.ui.Button) -> None:
        view = VanirView(self.bot, user=itx.user)
        view.add_item(BanDetachmentSelect(self.ctx, self.rows, self.current))
        embed = self.ctx.embed("Ban Users")
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


class TimeoutButton(discord.ui.Button[NewUsersPager]):
    def __init__(
        self,
        ctx: VanirContext,
        all_members: list[discord.Member],
        current: list[discord.Member],
    ) -> None:
        super().__init__(
            label="Timeout",
            style=discord.ButtonStyle.grey,
            emoji=str(EMOJIS["timeout"]),
        )
        self.ctx = ctx
        self.all_members = all_members
        self.current = current

    async def callback(self, itx: discord.Interaction) -> None:
        view = VanirView(self.ctx.bot, user=itx.user)
        view.add_item(TimeoutDetachmentSelect(self.ctx, self.all_members, self.current))
        await itx.response.send_message(view=view, ephemeral=True)


class KickButton(discord.ui.Button[NewUsersPager]):
    def __init__(
        self,
        ctx: VanirContext,
        all_members: list[discord.Member],
        current: list[discord.Member],
    ) -> None:
        super().__init__(
            label="Kick",
            style=discord.ButtonStyle.grey,
            emoji=str(EMOJIS["kick"]),
        )
        self.ctx = ctx
        self.all_members = all_members
        self.current = current

    async def callback(self, itx: discord.Interaction) -> None:
        view = VanirView(self.ctx.bot, user=itx.user)
        view.add_item(KickDetachmentSelect(self.ctx, self.all_members, self.current))
        await itx.response.send_message(view=view, ephemeral=True)


class BanButton(discord.ui.Button[NewUsersPager]):
    def __init__(
        self,
        ctx: VanirContext,
        all_members: list[discord.Member],
        current: list[discord.Member],
    ) -> None:
        super().__init__(
            label="Ban",
            style=discord.ButtonStyle.grey,
            emoji=str(EMOJIS["ban"]),
        )
        self.ctx = ctx
        self.all_members = all_members
        self.current = current

    async def callback(self, itx: discord.Interaction) -> None:
        view = VanirView(self.ctx.bot, user=itx.user)
        view.add_item(BanDetachmentSelect(self.ctx, self.all_members, self.current))
        await itx.response.send_message(view=view, ephemeral=True)


class TimeoutDetachmentSelect(discord.ui.Select[NewUsersPager]):
    def __init__(
        self,
        ctx: VanirContext,
        all_members: list[discord.Member],
        current: list[discord.Member],
    ) -> None:
        super().__init__(
            placeholder="Select members to timeout...",
            min_values=1,
            max_values=len(current),
            options=[
                discord.SelectOption(
                    label=f"{m.name[:80]} [{m.id}]",
                    value=str(m.id),
                )
                for m in current
            ],
        )
        self.ctx = ctx
        self.all_members = all_members

    async def callback(self, itx: discord.Interaction) -> None:
        input_time, *_ = await generate_modal(
            itx,
            "Timeout Duration",
            fields=[
                discord.ui.TextInput(
                    label="Duration [ie. '2 days', '2 hours 45 minutes']",
                    placeholder="Enter a duration...",
                    required=True,
                ),
            ],
        )
        until: datetime.datetime = parse_time(input_time)
        if until < datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1):
            msg = "Duration cannot be negative"
            raise ValueError(msg)

        if until > datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=28):
            msg = "Duration cannot be longer than 28 days [discord limit]"
            raise ValueError(msg)

        members = [
            discord.utils.get(self.all_members, id=int(member_id))
            for member_id in self.values
        ]
        for member in members:
            await member.timeout(
                until,
                reason=f"Timed out by {itx.user.name}",
            )

        embed = self.ctx.embed(
            title=f"Timed Out {len(members)} Member{'s' if len(members) > 1 else ''}",
            description=f"Will be unmuted... <t:{round(until.timestamp())}:R> [<t:{round(until.timestamp())}:F>]\n{"\n".join(f"- {m.mention} [`{m.id}`]" for m in members)}",
        )
        await itx.edit_original_response(embed=embed)


class KickDetachmentSelect(discord.ui.Select[NewUsersPager]):
    def __init__(
        self,
        ctx: VanirContext,
        all_members: list[discord.Member],
        current: list[discord.Member],
    ) -> None:
        super().__init__(
            placeholder="Select members to kick...",
            min_values=1,
            max_values=len(current),
            options=[
                discord.SelectOption(
                    label=f"{m.name[:80]} [{m.id}]",
                    value=str(m.id),
                )
                for m in current
            ],
        )
        self.ctx = ctx
        self.all_members = all_members

    async def callback(self, itx: discord.Interaction) -> None:
        member_ids = [int(v) for v in self.values]
        members = [
            discord.utils.get(self.all_members, id=member_id)
            for member_id in member_ids
        ]
        for member in members:
            await member.kick(reason=f"Kicked by {itx.user.name}")

        embed = self.ctx.embed(
            title=f"Kicked {len(member_ids)} Members",
            description="\n".join(f"{m.name} [{m.id}]" for m in members),
        )
        await itx.response.send_message(embed=embed, ephemeral=True)


class BanDetachmentSelect(discord.ui.Select[NewUsersPager]):
    def __init__(
        self,
        ctx: VanirContext,
        all_members: list[discord.Member],
        current: list[discord.Member],
    ) -> None:
        super().__init__(
            placeholder="Select members to ban...",
            min_values=1,
            max_values=len(current),
            options=[
                discord.SelectOption(
                    label=f"{m.name[:80]} [{m.id}]",
                    value=str(m.id),
                )
                for m in current
            ],
        )
        self.ctx = ctx
        self.all_members = all_members

    async def callback(self, itx: discord.Interaction) -> None:
        dur, *_ = await generate_modal(
            itx,
            "Delete messages in the last...",
            fields=[
                discord.TextInput(
                    label="Duration [ie. '15s', '2 hours 5 minutes', '1d', 'one week']",
                    placeholder="Enter a duration, or leave blank to not delete messages.",
                    required=False,
                ),
            ],
        )
        delete_after: datetime.datetime = parse_time(dur) if dur else None
        if delete_after and delete_after < datetime.datetime.now(tz=datetime.UTC):
            await itx.response.send_message(
                "Duration cannot be negative",
                ephemeral=True,
            )
            return

        delete_secs = (
            (delete_after - datetime.datetime.now(tz=datetime.UTC)).total_seconds()
            if delete_after
            else discord.utils.MISSING
        )

        member_ids = [int(v) for v in self.values]
        members = [
            discord.utils.get(self.all_members, id=member_id)
            for member_id in member_ids
        ]
        for member in members:
            await member.ban(
                delete_message_seconds=delete_secs,
                reason=f"Banned by {itx.user.name}",
            )

        embed = self.ctx.embed(
            title=f"Banned {len(member_ids)} Members",
            description="\n".join(f"{m.name} [{m.id}]" for m in members),
        )
        if delete_after:
            embed.description += (
                f"Deleting messages from the last {regress_time(delete_secs)}"
            )
        await itx.response.send_message(embed=embed, ephemeral=True)


class AvatarButton(discord.ui.Button):
    def __init__(
        self, member: discord.Member, method: Awaitable[discord.Embed]
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
        self, member: discord.Member, method: Awaitable[discord.Embed]
    ) -> None:
        super().__init__(
            label="Permissions",
            style=discord.ButtonStyle.grey,
            emoji=str(EMOJIS["shield"]),
        )
        self.member = member
        self.method = method

    async def callback(self, itx: discord.Interaction) -> None:
        await self.method(itx, self.member)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Server(bot))
