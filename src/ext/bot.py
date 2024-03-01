import inspect
import pathlib

import discord
from discord.ext import commands
from constants import GITHUB_ROOT

from src.types.command import VanirCog, VanirView
from src.util.command import vanir_command
from src.types.core import VanirContext, Vanir
from src.types.util import timed
from src.ext.info import Info


class Bot(VanirCog):
    """Commands that deal with the bot itself"""

    emoji = "\N{Robot Face}"

    @vanir_command()
    async def ping(self, ctx: VanirContext):
        """Check if the bot is down or having excessive delays"""
        delays = {
            "\N{Shinto Shrine} Discord Gateway": self.bot.latency,
            "\N{Earth Globe Americas} Web Requests": await timed(
                self.bot.session.get, "https://example.com"
            ),
            "\N{Elephant} PGSQL DB": await timed(
                self.bot.db_currency.con.fetchval, "SELECT 0"
            ),
        }
        embed = ctx.embed("\N{Table Tennis Paddle and Ball} Pong!")
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
    ):
        """Retrieves a command's full source code (from github.com/StatHusky13/Vanir)"""
        root = "https://github.com/StatHusky13/Vanir/tree/main"
        line_preview_limit = 40

        if item is not None:
            # attempt to find the object
            command = self.bot.get_command(item)
            if command is not None:
                path = inspect.getsourcefile(command.callback)
                lines, first_line_num = inspect.getsourcelines(command.callback)
            else:
                cog = self.bot.get_cog(item)
                if cog is None:
                    raise ValueError("Please enter a valid command, group, or module")
                path = inspect.getsourcefile(cog.__class__)
                lines, first_line_num = inspect.getsourcelines(cog.__class__)

            n_lines = len(lines)

            url_path = f"{path[path.index('src'):]}#L{first_line_num}-L{first_line_num+n_lines}"

            embed = ctx.embed(title=f"Source: {item}", url=GITHUB_ROOT + url_path)
            embed.add_field(
                name="File",
                value=f"`{pathlib.Path(path).relative_to(pathlib.Path('.').absolute())}`",
                inline=False,
            )
            embed.add_field(
                name="Lines",
                value=f"`{str(first_line_num).rjust(4, '0')}` to `{str(first_line_num + n_lines).rjust(4, '0')}` [`{n_lines}` lines]",
                inline=False,
            )

            # the lines are already '\n' postfix-ed
            snippet = "".join(l for l in lines[:line_preview_limit])[:4000]
            if n_lines > line_preview_limit:
                snippet += "\n... [Snippet Cut Off]"

            embed.description = f"```py\n{snippet}\n```"
            view = github_view(ctx.bot, url_path)

        else:
            embed = ctx.embed(title="My Source is All on GitHub!", url=root)
            view = github_view(ctx.bot)

        await ctx.reply(embed=embed, view=view)

    @vanir_command(aliases=["bot", "vanir"])
    async def info(self, ctx: VanirContext):
        """Who is this guy?"""
        embed = ctx.embed(
            title="I am Vanir, an advanced multi-purpose bot.",
            description=f"I was made by StatHusky13, and am still in development."
        )
        example_commands = (ctx.bot.get_command(c) for c in ("help", "translate", "starboard setup", "new"))
        embed.add_field(
            name="Example commands",
            value="\n".join(
                f"{ctx.prefix}{cmd.qualified_name}\n\t*{cmd.description or cmd.short_doc or 'No Description'}*"
                for cmd in example_commands
            )
        )
        await ctx.send(embed=embed)


def github_view(bot: Vanir, path: str = ""):
    view = VanirView(bot)
    view.add_item(
        discord.ui.Button(
            style=discord.ButtonStyle.url,
            url=GITHUB_ROOT + path,
            emoji="\N{Squid}"
            )
        )
    return view

async def setup(bot: Vanir):
    await bot.add_cog(Bot(bot))
