import asyncio
import inspect
import pathlib
import time
from asyncio import subprocess

import discord
from discord.ext import commands

from src.constants import ANSI, GITHUB_ROOT
from src.types.command import GitHubView, VanirCog, vanir_command
from src.types.core import Vanir, VanirContext
from src.types.util import timed
from src.util.format import natural_join


class Bot(VanirCog):
    """Commands that deal with the bot itself."""

    emoji = "\N{ROBOT FACE}"

    @vanir_command()
    async def ping(self, ctx: VanirContext) -> None:
        """Check if the bot is down or having excessive delays."""
        delays = {
            "\N{SHINTO SHRINE} Discord Gateway": self.bot.latency,
            "\N{EARTH GLOBE AMERICAS} Web Requests": await timed(
                self.bot.session.get,
                "https://example.com",
            ),
            "\N{ELEPHANT} PGSQL DB": await timed(
                self.bot.db_currency.pool.fetchval,
                "SELECT 0",
            ),
        }
        embed = ctx.embed("\N{TABLE TENNIS PADDLE AND BALL} Pong!")
        for name, delay in delays.items():
            embed.add_field(name=name, value=f"`{delay*1000:.3f}ms`", inline=False)

        await ctx.reply(embed=embed)

    @vanir_command(aliases=["src"])
    async def source(
        self,
        ctx: VanirContext,
        *,
        item: str = commands.param(
            description="The item to view. This can be a command or Module",
            default=None,
        ),
    ) -> None:
        """Retrieve a command's full source code (from `github.com/statikana/Vanir`)."""
        root = GITHUB_ROOT + "/tree/main"
        line_preview_limit = 30

        if item is not None:
            # attempt to find the object
            command = self.bot.get_command(item)
            if command is not None:
                path = inspect.getsourcefile(command.callback)
                lines, first_line_num = inspect.getsourcelines(command.callback)
            else:
                cog = self.bot.get_cog(item)
                if cog is None:
                    msg = "Please enter a valid command, group, or module"
                    raise ValueError(msg)
                path = inspect.getsourcefile(cog.__class__)
                lines, first_line_num = inspect.getsourcelines(cog.__class__)

            n_lines = len(lines)

            url_path = f"{path[path.index('src'):]}#L{first_line_num}-L{first_line_num+n_lines}"

            embed = ctx.embed(title=f"Source: {item}", url=f"{GITHUB_ROOT}/{url_path}")
            embed.add_field(
                name="\N{FLOPPY DISK} File",
                value=f"`{pathlib.Path(path).relative_to(pathlib.Path().absolute())}`",
                inline=False,
            )
            embed.add_field(
                name="\N{SCROLL} Lines",
                value=f"`{str(first_line_num).rjust(4, '0')}` to "
                f"`{str(first_line_num + n_lines).rjust(4, '0')}` [`{n_lines}` lines]",
                inline=False,
            )

            # the lines are already '\n' postfix-ed
            snippet = "".join(line for line in lines[:line_preview_limit])[:4000]
            if n_lines > line_preview_limit:
                snippet += "\n... [Snippet Cut Off] "

            embed.description = f"```py\n{snippet}\n```"
            view = GitHubView(ctx.bot, url_path)

        else:
            embed = ctx.embed(title="My Source is All on GitHub!", url=root)
            view = GitHubView(ctx.bot)

        await ctx.reply(embed=embed, view=view)

    @vanir_command(aliases=["bot", "vanir"])
    async def info(self, ctx: VanirContext) -> None:
        """Who is this guy?."""
        if ctx.bot.application.team:
            dev = natural_join(m.name for m in ctx.bot.application.team.members)
        else:
            dev = ctx.bot.application.owner.name
        embed = ctx.embed(
            title="I am Vanir, an advanced multi-purpose bot.",
            description=f"I was made by {dev}, and am still in development.",
        )
        embed.add_field(
            name="Prefixes",
            value="My prefixes are "
            f"{natural_join(self.bot.command_prefix(self.bot, ctx.message)[1:])}",
            inline=False,
        )
        n_user_commands = len(
            [
                v
                for v in self.bot.walk_commands()
                if isinstance(v, commands.HybridCommand) and not v.hidden
            ],
        )
        n_user_cogs = len(
            [
                c
                for c in self.bot.cogs.values()
                if not getattr(c, "hidden", False) and c.qualified_name != "Jishaku"
            ],
        )
        embed.add_field(
            name="Commands",
            value=f"I have `{n_user_cogs}` modules, among `{n_user_commands}` commands",
            inline=False,
        )
        uptime = int(
            time.time()
            - (discord.utils.utcnow() - self.bot.launch_time).total_seconds(),
        )
        rem, tot = (f"<t:{uptime}:{s}>" for s in ("R", "F"))
        embed.add_field(
            name=f"Most recent restart: {rem}",
            value=f"I've been online since {tot}",
            inline=False,
        )

        proc = await subprocess.create_subprocess_shell(
            # fmt: off
            # author [hash - relative time]
            # commit message
            cmd=f'git log -n 5 --pretty=format:"'
            f"{ANSI['white']}%an [{ANSI['cyan']}%h{ANSI['white']} - "
            f"{ANSI['red']}%ar{ANSI['white']}]%n"
            f"{ANSI['grey']}➥%s\"",
            # fmt: on
            stdout=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        out = (await proc.stdout.read()).decode("utf-8")

        embed.add_field(
            name="Recent Changes",
            value=f"```ansi\n{out}\n```[[view full change log here]]({GITHUB_ROOT + '/commits'})",
            inline=False,
        )
        view = GitHubView(self.bot)
        await ctx.send(embed=embed, view=view)

    @vanir_command(aliases=["up", "ut"])
    async def uptime(self, ctx: VanirContext) -> None:
        """Check how long I've been running."""
        uptime = int(
            time.time()
            - (discord.utils.utcnow() - self.bot.launch_time).total_seconds(),
        )
        rem, tot = (f"<t:{uptime}:{s}>" for s in ("R", "F"))
        embed = ctx.embed(
            title=f"I've been up since {rem}",
            description=f"Since: {tot}",
        )
        await ctx.reply(embed=embed)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Bot(bot))
