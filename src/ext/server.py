import discord
from discord.ext import commands

from src.types.command import VanirCog, AutoTablePager
from src.util.command import vanir_command
from src.types.core import VanirContext, Vanir


class Server(VanirCog):
    """Information about this server"""

    emoji = "\N{Hut}"

    @vanir_command()
    async def new(self, ctx: VanirContext):
        """Shows the list of all new members in the server"""
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)
        headers = ["name", "joined at"]
        dtypes = ["t", "t"]

        view = AutoTablePager(
            ctx.bot,
            ctx.author,
            headers=headers,
            rows=[[m.name, m.joined_at.strftime("%Y/%m/%d %H:%M:%S")] for m in members],
            dtypes=dtypes,
            rows_per_page=10,
            as_image=False,
        )

        embed, _ = await view.update_embed()
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


async def setup(bot: Vanir):
    await bot.add_cog(Server(bot))
