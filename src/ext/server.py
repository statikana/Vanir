import discord
from discord.ext import commands

from src.types.command import AutoTablePager, VanirCog, VanirView, vanir_command
from src.types.core import Vanir, VanirContext
from src.util.ux import generate_modal


class Server(VanirCog):
    """Information about this server"""

    emoji = "\N{HUT}"

    @vanir_command()
    async def new(self, ctx: VanirContext):
        """Shows the list of all new members in the server"""
        members: list[discord.Member] = sorted(
            ctx.guild.members, key=lambda m: m.joined_at, reverse=True
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
        view.add_item(TimeoutButton(ctx, members, view.current))
        view.add_item(KickButton(ctx, members, view.current))
        view.add_item(BanButton(ctx, members, view.current))
        embed = await view.update_embed()
        await view.update(update_content=False)
        view.message = await ctx.reply(embed=embed, view=view)

    @vanir_command(aliases=["clean"])
    @commands.has_permissions(manage_messages=True)
    async def cleanup(
        self,
        ctx: VanirContext,
        n_messages: commands.Range[int, 1, 100] = commands.param(
            description="How many messages to delete.", default=3
        ),
    ):
        """Purges a channel of bot messages or commands which prompted Vanir to respond"""
        await ctx.defer()
        messages = await ctx.channel.purge(
            limit=n_messages + 1,
            check=lambda m: m.author.bot
            or any(
                m.content.startswith(p)
                for p in ctx.bot.command_prefix(ctx.bot, ctx.message)
            ),
            reason=f"`\cleanup` by {ctx.author.name}",
        )

        embed = ctx.embed(f"Deleted {len(messages)} Messages")
        await ctx.send(embed=embed, delete_after=3)

    @vanir_command()
    async def nukeuser(
        self,
        ctx: VanirContext,
        member: discord.Member = commands.param(
            description="The member to delete messages from"
        ),
        max_messages: commands.Range[int, 0, 100] = commands.param(
            description="How far back into the history of a channel to search.",
            default=50,
        ),
        channel: discord.TextChannel = commands.param(
            description="The channel to delete messages from. If not provided, all channels will be searched.",
            default=None,
        ),
    ):
        """Deletes the last `max_messages` messages by a member in every channel"""
        await ctx.defer()
        if channel is None:
            data = {
                channel: 0
                for channel in ctx.guild.text_channels
                if (
                    channel.permissions_for(ctx.guild.me).manage_messages
                    or ctx.guild.me.guild_permissions.manage_messages
                )
                and (
                    channel.permissions_for(member).send_messages
                    or member.guild_permissions.send_messages
                )
            }
        else:
            data = {channel: 0}

        for channel in data:
            data[channel] = len(
                await channel.purge(
                    limit=max_messages,
                    check=lambda m: m.author == member,
                    reason=f"`\\nukeuser` by {ctx.author.name}",
                )
            )
        data = list(filter(lambda x: x[1] > 0, data.items()))

        embed = ctx.embed(
            title=f"Deleted {sum(v[1] for v in data)} messages by {member.name}",
            description="\n".join(f"{channel.mention}: {n}" for channel, n in data)
            or "No messages found",
        )
        await ctx.send(embed=embed)


class NewUsersPager(AutoTablePager):
    def __init__(
        self,
        ctx: VanirContext,
        rows: list[discord.Member],
    ):
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

    @discord.ui.button(
        label="Timeout...",
        style=discord.ButtonStyle.grey,
    )
    async def timeout(self, itx: discord.Interaction, button: discord.ui.Button):
        view = VanirView(self.bot, user=itx.user)
        view.add_item(TimeoutDetachmentSelect(self.ctx, self.rows, self.current))
        embed = self.ctx.embed("Timeout Users")
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Kick...",
        style=discord.ButtonStyle.red,
    )
    async def kick(self, itx: discord.Interaction, button: discord.ui.Button):
        view = VanirView(self.bot, user=itx.user)
        view.add_item(KickDetachmentSelect(self.ctx, self.rows, self.current))
        embed = self.ctx.embed("Kick Users")
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="Ban...",
        style=discord.ButtonStyle.red,
    )
    async def ban(self, itx: discord.Interaction, button: discord.ui.Button):
        view = VanirView(self.bot, user=itx.user)
        view.add_item(BanDetachmentSelect(self.ctx, self.rows, self.current))
        embed = self.ctx.embed("Ban Users")
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


class TimeoutDetachmentSelect(discord.ui.Select[NewUsersPager]):
    def __init__(
        self,
        ctx: VanirContext,
        all_members: list[discord.Member],
        current: list[discord.Member],
    ):
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

    async def callback(self, itx: discord.Interaction):
        time = await generate_modal(
            itx,
            "Timeout Duration",
            fields=[
                discord.TextInput(
                    label="Duration [ie. '15s', '2 hours', '1d', 'one week']",
                    placeholder="Enter a duration...",
                    required=True,
                )
            ],
        )
        member_ids = [int(v) for v in self.values]
        for member_id in member_ids:
            member = discord.utils.get(self.all_members, id=member_id)
            await member.edit()


async def setup(bot: Vanir):
    await bot.add_cog(Server(bot))
