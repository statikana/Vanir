import io
import time

import discord
from discord.ext import commands

from src.types.command import VanirCog, vanir_command, vanir_group
from src.types.core import Vanir, VanirContext
from src.types.piston import PistonExecutable, PistonPackage
from src.util.format import trim_codeblock
from src.util.ux import generate_modal


class Piston(VanirCog):
    @vanir_command(aliases=["eval"])
    async def exec(
        self,
        ctx: VanirContext,
        package: str = commands.param(
            description="The language to execute the code in",
            default=None,
        ),
        *,
        code: str | None = commands.param(
            description="The code to execute",
            default=None,
        ),
    ):
        """Execute code"""
        await ctx.defer()

        if code is None and ctx.interaction is not None:
            code, *_ = await generate_modal(
                ctx.interaction,
                "Enter code to execute",
                fields=[
                    discord.ui.TextInput(
                        placeholder="Enter code here",
                        min_length=1,
                        max_length=2000,
                    )
                ],
            )
        code = trim_codeblock(code)

        valid_runtimes = list(
            filter(
                lambda rt: rt.language.lower() == package.lower()
                or package.lower() in rt.aliases,
                await self.bot.piston.runtimes(),
            )
        )

        if not valid_runtimes:
            return await ctx.reply(f"No runtimes available for {package}")

        runtime = max(
            valid_runtimes,
            key=lambda rt: rt.version.split("."),
        )

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
                )
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
                )
            )
        else:
            embeds.append(
                ctx.embed(
                    title="stdout",
                    description=f"executed & compiled in `{exec_diff*1000:.2f}ms`\n```\n{out}```",
                )
            )

        if result.stderr:
            embeds.append(
                ctx.embed(
                    title="stderr",
                    description=f"```\n{result.stderr}```",
                    color=discord.Color.red(),
                )
            )

        await ctx.reply(embeds=embeds, files=files)

    @vanir_command()
    async def py(self, ctx: VanirContext, *, code: str):
        """Execute python code"""
        await self.exec(ctx, package="python", code=code)


async def setup(bot: Vanir):
    await bot.add_cog(Piston(bot))
