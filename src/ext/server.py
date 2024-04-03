from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from src.constants import EMOJIS
from src.types.command import (
    AutoTablePager,
    VanirCog,
    VanirContext,
    VanirView,
    vanir_command,
)
from src.util.regex import EMOJI_REGEX
from src.util.time import format_time, parse_time
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
            include_spacer_image=True,
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
        file = discord.File("assets/spacer.png", filename="spacer.png")
        embed.set_image(url="attachment://spacer.png")
        view.message = await ctx.reply(embed=embed, view=view, file=file)

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

    @vanir_command()
    async def snipe(
        self,
        ctx: VanirContext,
        index: commands.Range[int, 1, 30] = commands.param(
            description="The index of the message to snipe (1 is the most recent message)",
            default=1,
        ),
        channel: discord.TextChannel | None = commands.param(
            description="The channel to snipe",
            default=lambda ctx: ctx.channel,
            displayed_default="Current channel",
        ),
    ) -> None:
        """Snipes the last edited or deleted message in a channel."""
        try:
            snipes = self.bot.cache.snipes[channel.id]
        except KeyError as err:
            msg = "No messages to snipe."
            raise ValueError(msg) from err
        if not snipes:
            msg = "No messages to snipe."
            raise ValueError(msg)

        try:
            real_index = len(snipes) - index
            snipe = snipes[real_index]
        except IndexError as err:
            msg = f"No message at that index. I only have {len(snipes)} snipes stored for {channel.name}."
            raise ValueError(msg) from err

        snipe = snipes.pop()

        embed = ctx.embed(
            description=snipe.message.content,
        )
        embed.set_author(
            name=f"{snipe.message.author}",
            icon_url=snipe.message.author.display_avatar.url,
        )
        embed.timestamp = snipe.sniped_at
        embed.set_footer(
            text=f"{snipe.type.value} by {snipe.message.author} | Snipe {index}/{len(snipes)+1}",
        )

        filenames = []
        if snipe.message.attachments:
            for file in snipe.message.attachments:
                filenames.append(file.filename)
                if file.content_type.startswith("image"):
                    embed.set_image(url=file.url)

            embed.add_field(
                name="Attachments",
                value="\n".join(
                    f"[`{file.filename or "<no filename>"}`]({file.url})"
                    for file in snipe.message.attachments
                ),
            )

        if snipe.message.reference:
            ref = snipe.message.reference.resolved
            embed.add_field(
                name="Replied to",
                value=f"[`{ref.author}`]: {ref.content}",
            )

        embeds = [embed]
        embeds.extend(snipe.message.embeds)
        await ctx.send(embeds=embeds)


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
                f"Deleting messages from the last {format_time(delete_secs)}"
            )
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Server(bot))
