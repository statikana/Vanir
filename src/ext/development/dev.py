import asyncio

import aiohttp
import discord
from discord.ext import commands

from src.types.command import VanirCog
from src.types.core import Vanir, VanirContext
from src.types.piston import PistonPackage
from src.util.command import cog_hidden
from src.util.parse import unique


@cog_hidden
class Dev(VanirCog):
    @commands.group()
    @commands.is_owner()
    async def dev(self, ctx):
        """..."""
        pass

    @dev.command()
    async def sync(self, ctx: VanirContext, *, guild_id: str | None = None):
        """Syncs commands to discord"""
        if guild_id:
            cmds = await self.bot.tree.sync(guild=discord.Object(id=int(guild_id)))
        else:
            cmds = await self.bot.tree.sync()

        await ctx.reply(
            embed=ctx.embed("Synced", description=",".join(c.name for c in cmds))
        )

    @dev.command()
    async def desync(self, ctx: VanirContext):
        """Removes all commands, then syncs"""
        self.bot.recursively_remove_all_commands()
        await self.bot.tree.sync()
        await ctx.reply(str(ctx.bot.commands))

    @dev.command()
    async def echo(self, ctx: VanirContext, *, message: str):
        """Replies"""
        await ctx.reply(message)

    @dev.command()
    async def setbal(self, ctx: VanirContext, user: discord.User, amount: int):
        """Manually set user balance"""
        await self.bot.db_currency.set_balance(user.id, amount)
        await ctx.reply(f"{user.id} -> {amount}")

    @dev.command()
    async def sql(self, ctx: VanirContext, *, query: str):
        """Run a SQL query"""
        async with self.bot.pool.acquire() as conn:
            result = await conn.fetch(query)
            await ctx.reply(str(result))

    @dev.command(aliases=["dbg"])
    async def debug(self, ctx: VanirContext, val: bool | None = None):
        """Toggle debug mode"""
        if val is not None:
            self.bot.debug = val
        await ctx.reply(f"Debug mode is {self.bot.debug}")

    @dev.command()
    async def error(self, ctx: VanirContext):
        """Throw an error"""
        raise ValueError("This is a test error")

    @dev.command()
    async def git(self, ctx: VanirContext, *, message: str):
        """Does a git cycle"""
        out: dict[str, str | None] = {}
        err: dict[str, str | None] = {}
        for cmd in (
            ["add", "."],
            ["commit", "-m", message],
            ["push"],
        ):
            proc = await asyncio.create_subprocess_exec(
                "git",
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            ret = await proc.wait()
            if ret == 0:
                out[cmd[0]] = (await proc.stdout.read()).decode()
            else:
                err[cmd[0]] = (await proc.stderr.read()).decode()
                break

        embed = ctx.embed("git")
        embed.add_field(
            name="Output", value="\n".join(f"**{k}**\n{v}" for k, v in out.items())
        )
        embed.add_field(
            name="Error", value="\n".join(f"**{k}**\n{v}" for k, v in err.items())
        )
        await ctx.reply(embed=embed)

    @dev.command()
    async def piston(
        self,
        ctx: VanirContext,
        to_install: str | None = None,
        to_install_ver: str | None = None,
    ):
        if to_install is None:
            installed = sorted(await self.bot.piston.runtimes(), key=lambda x: (x.language, tuple(int(v) for v in x.version.split("."))))
            reg = sorted(await self.bot.piston.packages(), key=lambda x: (x.language, tuple(int(v) for v in x.language_version.split("."))))
            embeds = [
                ctx.embed(
                    "Available",
                    description=", ".join(
                        f"`{p.language} [{p.language_version}]`" for p in reg
                    ),
                ),
                ctx.embed(
                    "Installed",
                    description="\n".join(
                        f"`{p.language} [{p.version}]`" for p in installed
                    )
                    or "None",
                ),
            ]

            await ctx.reply(embeds=embeds)

        else:
            if to_install_ver is None:
                ver = max(
                    await self.bot.piston.packages(),
                    key=lambda x: tuple(x.language_version),
                ).language_version
            else:
                ver = to_install_ver
            await ctx.reply(f"Installing {to_install} {ver}")
            pkg = PistonPackage(language=to_install, language_version=ver)
            await self.bot.piston.install_package(pkg)
            await ctx.reply(f"Installed {to_install} {ver}")


async def setup(bot: Vanir):
    await bot.add_cog(Dev(bot))
