from __future__ import annotations

import asyncio
import difflib
import io
import time
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from src.constants import EMOJIS
from src.types.command import CloseButton, VanirCog, VanirView, vanir_command
from src.types.piston import PistonExecutable, PistonPackage, PistonRuntime
from src.util.format import trim_codeblock
from src.util.parse import fuzzysearch, language_from_codeblock, unique
from src.util.ux import generate_modal

if TYPE_CHECKING:
    from src.types.core import Vanir, VanirContext


class Code(VanirCog):
    """Code execution and formatting."""

    emoji = str(EMOJIS["piston"])

    @vanir_command(aliases=["eval"])
    async def exec(
        self,
        ctx: VanirContext,
        language: str = commands.param(
            description="The language to execute the code in",
            default=None,
        ),
        version: str = commands.param(
            description="The version of the language to execute the code in",
            default=None,
        ),
        *,
        code: str | None = commands.param(
            description="The code to execute",
            default=None,
        ),
    ) -> None:
        """Execute code."""
        if code is None:
            if ctx.interaction is not None:
                code, *_ = await generate_modal(
                    ctx.interaction,
                    "Enter code to execute",
                    fields=[
                        discord.ui.TextInput(
                            label=f"Enter {language} Code",
                            placeholder="Enter code here",
                            min_length=1,
                            max_length=2000,
                        ),
                    ],
                )
            else:
                try:
                    msg = await ctx.send("Send code...")
                    res: discord.Message = await ctx.bot.wait_for(
                        "message",
                        check=lambda m: m.author == ctx.author
                        and m.channel == ctx.channel,
                        timeout=300,
                    )
                    await msg.delete()
                    code = res.content

                except asyncio.TimeoutError as err:
                    msg = "Timed out waiting for code"
                    raise commands.CommandError(msg) from err

        if language is None:  # only happens in itx
            language = language_from_codeblock(self.bot, code)
            if language is None:
                msg = "No language specified"
                raise ValueError(msg)
        elif language.startswith("```"):
            language = language_from_codeblock(self.bot, language)
            if language is None:
                msg = "No language specified"
                raise ValueError(msg)

            code = f"```{version}\n{code}```\n"
            version = None

        else:
            for p in self.bot.installed_piston_packages:
                if p.language == language or language in p.aliases:
                    language = p.language
                    break
            else:
                msg = "Invalid language - please use the autocomplete menu to select a valid language."
                raise ValueError(msg)

        if version in (None, "latest"):
            version = max(
                (
                    rt.version
                    for rt in self.bot.installed_piston_packages
                    if rt.language == language
                ),
                key=lambda v: tuple(int(x) for x in v.split(".")),
            )
        else:
            version = version.strip("v`").lower()
            real_ver = discord.utils.find(
                lambda rt: rt.language == language
                and (rt.version == version or version in rt.aliases),
                self.bot.installed_piston_packages,
            )
            if real_ver is None:
                msg = f"Invalid version: {version}"
                raise ValueError(msg)
            version = real_ver.version

        code = code.replace("```", "\n```\n").strip("\n")

        if code.startswith("```"):
            code = code.split("\n", 1)[1]

        code = trim_codeblock(code).strip("\n `")

        runtime = discord.utils.get(
            self.bot.installed_piston_packages,
            language=language,
            version=version,
        )
        if runtime is None:
            msg = "No runtime found for language and version"
            raise RuntimeError(msg)

        start_time = time.perf_counter()
        response = await self.bot.piston.execute(
            package=PistonPackage(
                language=runtime.language,
                language_version=runtime.version,
            ),
            files=[
                PistonExecutable(
                    name="main",
                    content=code,
                ),
            ],
        )
        exec_diff = time.perf_counter() - start_time

        result = response.run
        embeds = []
        files = []
        out = result.stdout or "<<No output>>"

        input_embed = ctx.embed(
            title="Input",
            description=f"```{runtime.language}\n{code}```",
        )
        input_embed.set_footer(
            text=f"{runtime.language} {runtime.version}",
        )

        embeds.append(input_embed)

        if len(out) > 2000:
            files.append(
                discord.File(
                    io.BytesIO(out.encode()),
                    filename="output.txt",
                ),
            )
        else:
            embeds.append(
                ctx.embed(
                    title="stdout",
                    description=f"executed & compiled in `{exec_diff*1000:.2f}ms`\n```\n{out}```",
                ),
            )

        if result.stderr:
            embeds.append(
                ctx.embed(
                    title="stderr",
                    description=f"```\n{result.stderr}```",
                    color=discord.Color.red(),
                ),
            )
        view = AfterCodeExecView(ctx, runtime, code)
        await ctx.reply(embeds=embeds, files=files, view=view)

    @exec.autocomplete("language")
    async def _autocomplete_language(
        self,
        itx: discord.Interaction,
        argument: str,
    ) -> list[discord.app_commands.Choice]:
        return (
            fuzzysearch(
                argument,
                self.bot.installed_piston_packages,
                output=lambda rt: discord.app_commands.Choice(
                    name=rt.language,
                    value=rt.language,
                ),
                threshold=70,
            )[:25]
            if argument
            else [
                discord.app_commands.Choice(
                    name=rt.language,
                    value=rt.language,
                )
                for rt in unique(
                    self.bot.installed_piston_packages, key=lambda rt: rt.language
                )
            ][:25]
        )

    @exec.autocomplete("version")
    async def _autocomplete_version(
        self,
        itx: discord.Interaction,
        argument: str,
    ) -> list[discord.app_commands.Choice]:
        language = itx.namespace.__dict__.get("language")
        if language is None or language not in [
            p.language for p in self.bot.installed_piston_packages
        ]:
            return [
                discord.app_commands.Choice(name="No valid package selected", value=""),
            ]

        return [
            discord.app_commands.Choice(
                name=rt.version,
                value=rt.version,
            )
            for rt in self.bot.installed_piston_packages
            if rt.language == language
        ][:25]

    def fmtpack(self, rt: PistonRuntime) -> str:
        return f"{rt.language} {rt.version}"

    @vanir_command(aliases=["python"])
    async def py(
        self,
        ctx: VanirContext,
        *,
        code: str | None = commands.param(
            description="The code to execute",
            default=None,
        ),
    ) -> None:
        """Execute python code."""
        await self.exec(ctx, package="python", code=code)

    @vanir_command()
    async def math(
        self,
        ctx: VanirContext,
        *,
        code: str | None = commands.param(
            description="The code to execute",
            default=None,
        ),
    ) -> None:
        """Math via python."""
        lines = trim_codeblock(code).splitlines()
        last = lines[-1]
        if last.count("(") == last.count(")") and "print" not in last:
            last = f"print({last})"
        code = "\n".join(lines[:-1] + [last])
        code = f"""
from math import *
{code}
"""
        await self.exec(ctx, package="python", code=code)

    @vanir_command(aliases=["fmt", "ruff"])
    async def format(
        self,
        ctx: VanirContext,
        *,
        python_code: str | None = commands.param(
            description="The code to format",
            default=None,
        ),
        diff: bool = commands.param(
            description="Show diff instead of new code",
            default=True,
        ),
    ) -> None:
        """Format your python code with ruff."""
        if isinstance(python_code, commands.Parameter):
            python_code = python_code.default
        if isinstance(diff, commands.Parameter):
            diff = diff.default

        if python_code is None:
            if ctx.interaction is not None:
                python_code, *_ = await generate_modal(
                    ctx.interaction,
                    "Enter code to format",
                    fields=[
                        discord.ui.TextInput(
                            label="Enter Python Code",
                            placeholder="Enter code here",
                            min_length=1,
                            max_length=2000,
                        ),
                    ],
                )
            else:
                try:
                    msg = await ctx.send("Send code...")
                    res: discord.Message = await ctx.bot.wait_for(
                        "message",
                        check=lambda m: m.author == ctx.author
                        and m.channel == ctx.channel,
                        timeout=300,
                    )
                    await msg.delete()
                    python_code = res.content

                except asyncio.TimeoutError as err:
                    msg = "Timed out waiting for code"
                    raise commands.CommandError(msg) from err

        python_code = trim_codeblock(python_code)
        start_time = time.perf_counter()
        command = "py -m ruff format -"

        shell = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await shell.communicate(python_code.encode())
        exec_diff = time.perf_counter() - start_time

        out = stdout.decode()
        if diff:
            out = self.diff_formatter(python_code, out)
        err = stderr.decode()

        if len(out) > 4000:
            files = [
                discord.File(
                    io.BytesIO(out.encode()),
                    filename="output.diff" if diff else "output.txt",
                ),
            ]
            embeds = [
                ctx.embed(
                    title="Input",
                    description=f"```python\n{python_code}```"[:4000],
                ),
                ctx.embed(
                    title="Output",
                    description=f"completed in `{exec_diff*1000:.2f}ms",
                ),
            ]
        else:
            embeds = [
                ctx.embed(
                    title="Input",
                    description=f"```python\n{python_code}```"[:4000],
                ),
                ctx.embed(
                    title="Output",
                    description=f"completed in `{exec_diff*1000:.2f}ms`\n```diff\n{out}```",
                ),
            ]
            files = []

        if err:
            if len(err) > 4000:
                files.append(
                    discord.File(
                        io.BytesIO(err.encode()),
                        filename="stderr.txt",
                    ),
                )
            else:
                embeds.append(
                    ctx.embed(
                        title="stderr",
                        description=f"```\n{err}```",
                        color=discord.Color.red(),
                    ),
                )

        await ctx.reply(embeds=embeds, files=files)

    def diff_formatter(self, old: str, new: str) -> str:
        diff = difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="old",
            tofile="new",
        )
        return "\n".join(diff)


class AfterCodeExecView(VanirView):
    def __init__(
        self,
        ctx: VanirContext,
        runtime: PistonRuntime,
        code: str,
    ) -> None:
        super().__init__(bot=ctx.bot, user=ctx.author)
        self.ctx = ctx
        self.runtime = runtime
        self.code = code

        self.add_item(CloseButton())

    @discord.ui.button(
        emoji="\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}",
        style=discord.ButtonStyle.primary,
    )
    async def run_again(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        message = discord.utils.get(self.bot.cached_messages, id=self.ctx.message.id)
        if message is None:
            message = await self.ctx.channel.fetch_message(self.ctx.message.id)
        if message is None:
            return
        await itx.message.delete()
        self.ctx.message.content = message.content
        await self.ctx.bot.process_commands(self.ctx.message)  # probably works


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Code(bot))
