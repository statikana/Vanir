from __future__ import annotations

import asyncio
import importlib
import time
from typing import TYPE_CHECKING, NoReturn

import aiohttp
import discord
from discord.ext import commands

from src.types.command import VanirCog
from src.types.piston import PistonPackage
from src.util.command import cog_hidden

if TYPE_CHECKING:
    from src.types.core import Vanir, VanirContext


@cog_hidden
class Dev(VanirCog):
    @commands.group()
    @commands.is_owner()
    async def dev(self, ctx: VanirContext) -> None:
        """..."""

    @dev.command()
    async def sync(self, ctx: VanirContext, *, guild_id: str | None = None) -> None:
        """Sync commands to discord."""
        if guild_id:
            cmds = await self.bot.tree.sync(guild=discord.Object(id=int(guild_id)))
        else:
            cmds = await self.bot.tree.sync()

        await ctx.reply(
            embed=ctx.embed("Synced", description=",".join(c.name for c in cmds)),
        )

    @dev.command()
    async def desync(self, ctx: VanirContext) -> None:
        """Remove all commands, then syncs."""
        self.bot.recursively_remove_all_commands()
        await self.bot.tree.sync()
        await ctx.reply(str(ctx.bot.commands))

    @dev.command()
    async def echo(self, ctx: VanirContext, *, message: str) -> None:
        """Reply."""
        await ctx.reply(message)

    @dev.command()
    async def setbal(self, ctx: VanirContext, user: discord.User, amount: int) -> None:
        """Manually set user balance."""
        await self.bot.db_currency.set_balance(user.id, amount)
        await ctx.reply(f"{user.id} -> {amount}")

    @dev.command()
    async def sql(self, ctx: VanirContext, *, query: str) -> None:
        """Run a SQL query."""
        async with self.bot.pool.acquire() as conn:
            result = await conn.fetch(query)
            await ctx.reply(str(result))

    @dev.command(aliases=["dbg"])
    async def debug(self, ctx: VanirContext, val: bool | None = None) -> None:
        """Toggle debug mode."""
        if val is not None:
            self.bot.debug = val
        await ctx.reply(f"Debug mode is {self.bot.debug}")

    @dev.command()
    async def error(self, ctx: VanirContext) -> NoReturn:
        """Throw an error."""
        msg = "This is a test error"
        raise ValueError(msg)

    @dev.command()
    async def git(self, ctx: VanirContext, *, message: str) -> None:
        """Do a git cycle."""
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
            name="Output",
            value="\n".join(f"**{k}**\n{v}" for k, v in out.items()),
        )
        embed.add_field(
            name="Error",
            value="\n".join(f"**{k}**\n{v}" for k, v in err.items()),
        )
        await ctx.reply(embed=embed)

    @dev.command()
    async def piston(
        self,
        ctx: VanirContext,
        to_install: str | None = None,
        to_install_ver: str | None = None,
    ) -> None:
        if to_install is None:
            installed = sorted(
                await self.bot.piston.runtimes(),
                key=lambda x: (x.language, tuple(int(v) for v in x.version.split("."))),
            )
            reg = sorted(
                await self.bot.piston.packages(),
                key=lambda x: (
                    x.language,
                    tuple(int(v) for v in x.language_version.split(".")),
                ),
            )
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
            return None

        else:
            pkgs = await self.bot.piston.packages()

            relevant = list(
                filter(
                    lambda x: x.language.lower() == to_install.lower(),
                    pkgs,
                ),
            )

            if not relevant:
                return await ctx.reply(f"`No packages found for {to_install}`")

            if to_install_ver in (None, "latest"):
                vers = [
                    max(
                        relevant,
                        key=lambda x: tuple(
                            int(v) for v in x.language_version.split(".")
                        ),
                    ).language_version,
                ]
            elif to_install_ver in (pkg.language_version for pkg in relevant):
                vers = [to_install]
            elif to_install_ver in ("all", "*"):
                vers = [pkg.language_version for pkg in relevant]
            else:
                return await ctx.reply(
                    f"`invalid version spec: {to_install_ver} [latest, all, or specific version]`",
                )
            for ver in vers:
                pkg = PistonPackage(language=to_install, language_version=ver)
                msg = await ctx.send(
                    f"`...installing {pkg.language} {pkg.language_version}`",
                )
                start = time.perf_counter()
                try:
                    await self.bot.piston.install_package(pkg)
                except aiohttp.ClientResponseError as e:
                    await msg.edit(
                        content=f"`Failed to install {pkg.language} {pkg.language_version}: {e}`",
                    )
                else:
                    end = time.perf_counter()
                    await msg.edit(
                        content=f"`Installed {pkg.language} {pkg.language_version} in {end - start:.2f}s`",
                    )
                finally:
                    await asyncio.sleep(1)
            return None

    @dev.command()
    async def fmt(self, ctx: VanirContext) -> None:
        # run ./fmt.bat
        proc = await asyncio.create_subprocess_exec(
            "cmd",
            "/c",
            "fmt.bat",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        embed = ctx.embed("fmt")
        embed.add_field(name="Output", value=out.decode())
        embed.add_field(name="Error", value=err.decode(), inline=False)

        await ctx.reply(embed=embed)

    @commands.command(aliases=["r"])
    @commands.is_owner()
    async def reload(self, ctx: VanirContext, *, cog_only: bool = True) -> None:
        """Reload the bot."""
        log = []
        # first reload all utils and type containers
        if not cog_only:
            import src.util

            for mod in src.util.MODULE_PATHS:
                importlib.reload(importlib.import_module(mod))
                log.append(f"... `{mod}`")
            log.append("__Reloaded utils__\n")

            import src.types

            for mod in src.types.MODULE_PATHS:
                importlib.reload(importlib.import_module(mod))
                log.append(f"... `{mod}`")
            log.append("__Reloaded types__\n")

        # then reload all cogs
        exts = list(
            self.bot.extensions.keys(),
        )  # keysview will change during iteration, -> RuntimeError
        for ext in exts:
            await self.bot.reload_extension(ext)
            log.append(f"... `{ext}`")
        log.append("__Reloaded cogs__\n")

        embed = ctx.embed("Reloaded")
        embed.description = "\n".join(log)
        await ctx.send(embed=embed)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Dev(bot))
