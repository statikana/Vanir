import inspect
import pathlib

import discord
from discord.ext import commands

from src.types.command import VanirCog, vanir_command, VanirView
from src.types.core import VanirContext, Vanir
from src.types.util import timeit


class Bot(VanirCog):
    """Commands that deal with the bot itself"""

    emoji = "\N{Robot Face}"

    @vanir_command()
    async def ping(self, ctx: VanirContext):
        """Check if the bot is down or having excessive delays"""
        delays = {
            "\N{Shinto Shrine} Discord Gateway": self.bot.latency,
            "\N{Earth Globe Americas} Web Requests": await timeit(
                self.bot.session.get, "https://example.com"
            ),
            "\N{Elephant} PGSQL DB": await timeit(
                self.bot.db_currency.con.fetchval, "SELECT 0"
            ),
        }
        embed = ctx.embed("\N{Table Tennis Paddle and Ball} Pong!")
        for name, delay in delays.items():
            embed.add_field(name=name, value=f"`{delay*1000:.3f}ms`", inline=False)

        await ctx.send(embed=embed)

    @vanir_command()
    async def source(self, ctx: VanirContext, *, item: str = commands.param(description="The item to view. This can be a command or Module", default=None)):
        root = "https://github.com/StatHusky13/Vanir/tree/main"
        line_preview_limit = 25

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
        embed.add_field(name="File", value=f"`{pathlib.Path(path).name}`", inline=False)
        embed.add_field(
            name="Lines",
            value=f"`{str(first_line_num).rjust(4, '0')}` to `{str(first_line_num + n_lines).rjust(4, '0')}` [`{n_lines}` lines]",
            inline=False,
        )

        # the lines are already '\n' postfix
        snippet = "".join(l for l in lines[:line_preview_limit])[:1024]
        if n_lines > line_preview_limit:
            snippet += "\n... [Snippet Cut Off]"
        embed.add_field(name="Code Preview", value=f"```py\n{snippet}\n```")

        view = VanirView()
        view.add_item(
            discord.ui.Button(
                url=full_url, style=discord.ButtonStyle.success, label="View on GitHub"
            )
        )

        await ctx.send(embed=embed, view=view)


async def setup(bot: Vanir):
    await bot.add_cog(Bot(bot))
