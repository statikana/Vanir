import inspect
import pathlib

import discord
from discord.ext import commands

from src.types.command import VanirCog, VanirView
from src.util.command import vanir_command
from src.types.core import VanirContext, Vanir
from src.types.util import timed


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

            full_url = f"{root}/{path[path.index('src'):]}#L{first_line_num}-L{first_line_num+n_lines}"

            embed = ctx.embed(title=f"Source: {item}", url=full_url)
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

            # the lines are already '\n' postfix
            snippet = "".join(l for l in lines[:line_preview_limit])[:4000]
            if n_lines > line_preview_limit:
                snippet += "\n... [Snippet Cut Off]"

            embed.description = f"```py\n{snippet}\n```"

            view = VanirView(ctx.bot)
            view.add_item(
                discord.ui.Button(
                    url=full_url, label="View on GitHub", emoji="\N{Squid}"
                )
            )

        else:
            embed = ctx.embed(title="My Source is All on GitHub!", url=root)
            view = VanirView(ctx.bot)
            view.add_item(
                discord.ui.Button(url=root, label="View on GitHub", emoji="\N{Squid}")
            )

        await ctx.reply(embed=embed, view=view)


async def setup(bot: Vanir):
    await bot.add_cog(Bot(bot))
