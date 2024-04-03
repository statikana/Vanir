from __future__ import annotations

import asyncio
import inspect
import os
import pathlib
import platform
import shutil
import sys
import time
from asyncio import subprocess
from typing import TYPE_CHECKING

import cpuinfo
import discord
import GPUtil
import psutil
from discord.ext import commands

from src.constants import ANSI, EMOJIS, GITHUB_ROOT
from src.types.command import GitHubView, VanirCog, vanir_command
from src.types.util import timed
from src.util.cache import timed_lru_cache
from src.util.format import format_children, format_size, natural_join

if TYPE_CHECKING:
    from src.types.core import Vanir, VanirContext


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

    @vanir_command(name="shutil", aliases=["os", "sys"])
    async def sysinfo(
        self,
        ctx: VanirContext,
    ) -> None:
        """Display system information. Recaches every minute."""
        await ctx.typing()

        # if the cache is empty, fill it by awaiting get_info()
        # if not, do a dry call to get_info() to obtain the fields

        embed = ctx.embed(title="System Information")
        start = time.perf_counter()
        fields = await asyncio.to_thread(get_info)

        for field in fields:
            embed.add_field(
                name=field.name,
                value=field.value,
                inline=field.inline,
            )
        end = time.perf_counter()

        embed.set_footer(text=f"Fetched in {(end-start)*1000:.4f}ms")

        await ctx.reply(embed=embed)


@timed_lru_cache(seconds=60)
def get_info() -> list[discord.embeds._EmbedFieldProxy]:
    major, minor, micro = sys.version_info[:3]
    disk = shutil.disk_usage("/")

    d_total, d_free, d_used = (x / 1024**3 for x in disk)

    v_total, v_avail, v_per, v_used, v_free = (
        x / 1024**3 for x in psutil.virtual_memory()
    )

    cpu_avg_util = (
        sum(psutil.cpu_percent(interval=None, percpu=True)) / psutil.cpu_count()
    )

    gpu: GPUtil.GPU = GPUtil.getGPUs()[0]

    embed = discord.Embed(
        title="System Information",
    )

    # software
    name, value = format_children(
        emoji=EMOJIS["software"],
        title="Software",
        children=[
            ("Platform", f"`{platform.system()} {platform.release()}`"),
            ("Py Impl", f"`{sys.implementation.name}`"),
            ("Py Build", f"{major}.{minor}.{micro} {sys.version_info.releaselevel}"),
        ],
        as_field=True,
    )
    embed.add_field(name=name, value=value)

    # hardware utilization
    name, value = format_children(
        emoji=EMOJIS["gear"],
        title="Hardware Utilization",
        children=[
            ("CPU", f"`{os.cpu_count()} core [{cpu_avg_util:.2f}% avg.]`"),
            ("Disk", f"`{d_used:.2f}/{d_total:.2f} GiB`"),
            ("RAM", f"`{v_used:.2f}/{v_total:.2f} GiB`"),
        ],
        as_field=True,
    )
    embed.add_field(name=name, value=value)

    # spacer
    embed.add_field(name="ㅤ", value="ㅤ")

    # hardware specifiations
    cpu_info = cpuinfo.get_cpu_info()

    name, value = format_children(
        emoji=EMOJIS["cpu"],
        title="CPU Information",
        children=[
            ("Brand", f"`{cpu_info['brand_raw']}`"),
            ("Cores", f"`{cpu_info['count']} [{cpu_info['bits']}bit]`"),
            ("Frequency", f"`{cpu_info['hz_actual_friendly']}`"),
            ("Version", f"`{cpu_info['cpuinfo_version_string']}`"),
            ("Architecture", f"`{cpu_info['arch_string_raw']} [{cpu_info['arch']}]`"),
            (
                "Caches",
                f"`{format_size(cpu_info['l2_cache_size'])} L2, {format_size(cpu_info['l3_cache_size'])} L3`",
            ),
        ],
        as_field=True,
    )
    embed.add_field(name=name, value=value, inline=False)

    name, value = format_children(
        emoji=EMOJIS["gpu"],
        title="GPU Information",
        children=[
            ("Name", f"`{gpu.name}`"),
            ("Memory", f"`{gpu.memoryUsed/1000:.2f}/{gpu.memoryTotal/1000:.2f} GiB`"),
            ("Utilization", f"`{gpu.load*100:.2f}%`"),
            ("Temperature", f"`{gpu.temperature}°C`"),
        ],
        as_field=True,
    )
    embed.add_field(name=name, value=value, inline=False)
    return embed.fields


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Bot(bot))
