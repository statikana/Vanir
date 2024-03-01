import re
from asyncio import iscoroutinefunction
from typing import Callable, Any
import texttable

import discord
from discord import InteractionResponse
from discord.ext import commands

from src.constants import (
    VALID_IMAGE_FORMATS,
    GLOBAL_CHANNEL_PERMISSIONS,
    VOICE_CHANNEL_PERMISSIONS,
    TEXT_CHANNEL_PERMISSIONS,
    ALL_PERMISSIONS,
)
from src.types.command import (
    VanirCog,
    AutoCachedView,
)
from src.types.core import VanirContext, Vanir
from src.util.pregex import EMOJI_REGEX, SNOWFLAKE_REGEX

from src.util.command import (
    discover_cog,
    discover_group,
    get_display_cogs,
    get_param_annotation,
    vanir_command,
)
from src.util.fmt import format_dict, fbool
from src.util.parse import closest_name, find_filename, find_ext

import unicodedata


class Info(VanirCog):
    """What's this?"""

    emoji = "\N{White Question Mark Ornament}"

    @vanir_command()
    @commands.cooldown(4, 60, commands.BucketType.user)
    async def help(self, ctx: VanirContext):
        """Stop it, get some help"""

        # Cogs -> Modules
        embed = await self.get_cog_display_embed(ctx)
        sel = CogDisplaySelect(ctx, self)

        view = AutoCachedView(self.bot, user=ctx.author, items=[sel])

        await ctx.reply(embed=embed, view=view)

    @vanir_command(aliases=["sf", "id"])
    @commands.cooldown(5, 120, commands.BucketType.user)
    async def snowflake(
        self,
        ctx: VanirContext,
        snowflake: str = commands.param(
            description="The snowflake (ID) to get information on"
        ),
        search: bool = commands.param(
            description="Whether or not to search for the object who owns this ID. If this False, there is no cooldown for this command",
            default=True,
        ),
    ):
        """Gets information on a snowflake (ID). You can access when using Developer mode in Discord"""

        if not SNOWFLAKE_REGEX.fullmatch(snowflake):
            raise ValueError("Not a snowflake.")
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
            description="The characters to evaluate. Gets cut off at 30"
        ),
    ):
        """Get detailed information about unicode characters"""
        custom_emojis = EMOJI_REGEX.findall(chars)
        if custom_emojis:
            embed = ctx.embed(
                description="\n".join(
                    f"Custom Emoji: `{name}` [ID: `{emoji_id}`, Animated: {'Yes' if a else 'No'}]"
                    for a, name, emoji_id in custom_emojis
                )
            )
        else:
            codepoints: list[str] = []
            hotlinks: list[str] = []

            for c in chars[:40]:
                full_name = unicodedata.name(c, "<NOT FOUND>")

                codepoint = hex(ord(c))[2:].rjust(4, "0")
                codepoints.append(codepoint)

                info_base = f"https://unicodeplus.com/U+"
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

    async def scan_methods(
        self, ctx: VanirContext, method: str, attr: str, snowflake: int
    ):
        if attr == "message":
            received = discord.utils.find(
                lambda m: m.id == snowflake, ctx.bot.cached_messages
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

        embed = await getattr(self, f"{attr}_info_embed")(ctx, received)
        await ctx.reply(embed=embed)
        return True

    async def maybecoro_get(self, method: Callable[[int], Any], snowflake: int):
        if iscoroutinefunction(method):
            received = await method(snowflake)
        else:
            received = method(snowflake)
        return received

    async def user_info_embed(self, ctx: VanirContext, user: discord.User):
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
            value=f"\n".join(
                f"- {guild.name} [ID: `{guild.id}`]" for guild in user.mutual_guilds[:7]
            ),
            inline=False,
        )
        data = {
            "Bot?": user.bot,
            "System?": user.system,
        }

        if member is not None:
            data.update({"Color": closest_name(str(member.color)[1:])[0].title()})

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
        self, ctx: VanirContext, channel: discord.abc.GuildChannel
    ):
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

    async def message_info_embed(self, ctx: VanirContext, msg: discord.Message):
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
                    {"Roles": " ".join(o.mention for o in msg.role_mentions)}
                )
            if msg.channel_mentions:
                mentions.update(
                    {"Channels": " ".join(o.mention for o in msg.channel_mentions)}  # type: ignore
                )

            if mentions:
                embed.add_field(name="Mentions", value=format_dict(mentions))

            emojis = re.findall(EMOJI_REGEX, msg.content)
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

        data = {"Channel": f"{msg.channel.name} [ID: `{msg.channel.id}`]"}
        embed.set_footer(text=msg.author.name, icon_url=msg.author.display_avatar.url)
        return embed

    async def guild_info_embed(self, ctx: VanirContext, guild: discord.Guild):
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
                    guild.premium_subscribers, key=lambda m: m.premium_since
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

    async def role_info_embed(self, ctx: VanirContext, role: discord.Role):
        embed = ctx.embed(f"Role: {role.name}")

        embed.description = await self.get_permission_table(
            {f"'{role.name[:20]}'": role.permissions}, checked=ALL_PERMISSIONS
        )

        return embed

    async def emoji_info_embed(
        self, ctx: VanirContext, emoji: discord.Emoji | discord.PartialEmoji
    ):
        if isinstance(emoji, discord.PartialEmoji):
            emoji = await ctx.guild.fetch_emoji(emoji.id)

        embed = ctx.embed(title=f"Emoji: {emoji.name}")
        embed.set_image(url=emoji.url)

        embed.add_field(name="Created By", value=emoji.user)
        embed.add_field(name="Animated?", value=emoji.animated)
        return embed

    async def get_permission_table(
        self, permissions: dict[str, discord.Permissions], *, checked: list[str]
    ) -> str:
        table = texttable.Texttable(max_width=0)

        table.header(["permission"] + [n for n in permissions.keys()])
        table.set_header_align(["r"] + (["l"] * (len(permissions))))
        table.set_cols_align(["r"] + (["l"] * (len(permissions))))
        table.set_cols_dtype(["t"] + (["b"] * (len(permissions))))

        table.set_deco(
            texttable.Texttable.BORDER
            | texttable.Texttable.HEADER
            | texttable.Texttable.VLINES
        )
        for name in checked:
            table.add_row(
                [
                    name.replace("_", " ").title(),
                    *(getattr(p, name) for p in permissions.values()),
                ]
            )
        drawn = table.draw()
        drawn = drawn.replace("True", f"{fbool(True)} ").replace(
            "False", f"{fbool(False)}   "
        )
        return f"**```ansi\n{drawn}```**"

    async def add_permission_data_from_channel(
        self, ctx: VanirContext, embed: discord.Embed, channel: discord.abc.GuildChannel
    ):
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
            {"you": you, "me": me, "default": default}, checked=permission_to_check
        )
        embed.description += "\n" + data

    async def snowflake_info_embed(self, ctx: VanirContext, snowflake: int):
        embed = ctx.embed("No Object Found")
        await self.add_sf_data(embed, snowflake)
        return embed

    async def add_sf_data(self, embed: discord.Embed, snowflake: int):
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

    async def get_cog_display_embed(self, ctx: VanirContext) -> discord.Embed:
        embed = ctx.embed(
            title="Module Select",
        )

        cogs = get_display_cogs(self.bot)
        for c in cogs:
            embed.add_field(
                name=f"{getattr(c, 'emoji')} {c.qualified_name}",
                value=f"*{c.description or 'No Description'}*",
                inline=True,
            )

        return embed

    async def get_cog_info_embed(
        self, itx: discord.Interaction, cog: commands.Cog
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f"Module Info: **{cog.qualified_name}**",
            description=f"*{cog.description or 'No Description'}*",
            user=itx.user,
        )

        other_commands: list[commands.Command] = []

        for c in cog.get_commands():
            if isinstance(c, commands.Group):
                embed.add_field(
                    name=f"`{c.qualified_name}` Commands",
                    value="\n".join(
                        f"`/{sub.qualified_name}`" for sub in discover_group(c)
                    ),
                )
            else:
                other_commands.append(c)

        if other_commands:
            embed.add_field(
                name=f"{len(other_commands)} Miscellaneous Command{'s' if len(other_commands) > 1 else ''}",
                value="\n".join(f"`/{o.qualified_name}`" for o in other_commands),
            )

        return embed

    async def get_command_info_embed(
        self, itx: discord.Interaction, command: commands.Command
    ) -> discord.Embed:
        embed = VanirContext.syn_embed(
            title=f"Info: `/{command.qualified_name} {command.signature}`",
            description=f"*{command.description or command.short_doc or 'No Description'}*",
            user=itx.user,
        )

        for name, param in command.params.items():
            data = {"Required": "Yes" if param.required else "No"}
            if not param.required:
                data["Default"] = param.displayed_default or param.default
            embed.add_field(
                name=f"__`{name}`__: `{get_param_annotation(param)}`",
                value=f"*{param.description}*\n{format_dict(data)}",
                inline=False,
            )

        return embed

    async def get_command_info_select(
        self, ctx: VanirContext, command: commands.Command
    ):
        return CogInfoSelect(ctx, self, command.cog)


class CogDisplaySelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays all cogs in the bot"""

    def __init__(self, ctx: VanirContext, instance: Info):
        self.ctx = ctx
        self.instance = instance
        options = [
            discord.SelectOption(
                label=c.qualified_name,
                description=c.description or "No Description",
                value=c.qualified_name,
                emoji=getattr(c, "emoji"),
            )
            for c in get_display_cogs(self.ctx.bot)
        ]
        super().__init__(options=options, placeholder="Select a Module", row=0)

    async def callback(self, itx: discord.Interaction):
        """Goes to `cog info`"""
        # print("COG DISPLAY SELECT cb")
        await self.view.collect(itx)
        selected = self.values[0]
        cog = self.ctx.bot.get_cog(selected)

        embed = await self.instance.get_cog_info_embed(itx, cog)
        sel = CogInfoSelect(self.ctx, self.instance, cog)

        self.view.remove_item(self)
        self.view.add_item(sel)

        await InteractionResponse(itx).defer()
        await itx.message.edit(embed=embed, view=self.view)


class CogInfoSelect(discord.ui.Select[AutoCachedView]):
    """Creates a select which displays commands in a cog"""

    def __init__(self, ctx: VanirContext, instance: Info, cog: commands.Cog):
        self.ctx = ctx
        self.instance = instance
        options = [
            discord.SelectOption(
                label=c.qualified_name,
                description=f"{c.description or c.short_doc or 'No Description'}",
                value=c.qualified_name,
            )
            for c in discover_cog(cog)
        ]
        super().__init__(options=options, placeholder="Select a Command", row=0)

    async def callback(self, itx: discord.Interaction):
        """Goes to `command info`"""
        await self.view.collect(itx)
        selected = self.values[0]
        command = self.ctx.bot.get_command(selected)

        embed = await self.instance.get_command_info_embed(itx, command)
        sel = await self.instance.get_command_info_select(self.ctx, command)

        self.view.remove_item(self)
        self.view.add_item(sel)

        await InteractionResponse(itx).defer()
        await itx.message.edit(embed=embed, view=self.view)


async def setup(bot: Vanir):
    await bot.add_cog(Info(bot))
