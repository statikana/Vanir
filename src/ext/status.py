import io

import discord
from discord.ext import commands
from matplotlib import pyplot as plt

from src.types.command import VanirCog, vanir_command
from src.types.core import Vanir, VanirContext
from src.util.time import parse_time


class Status(VanirCog):
    emoji = "📊"

    @vanir_command(aliases=["hist", "histo"])
    async def histogram(
        self,
        ctx: VanirContext,
        member: discord.Member = commands.param(
            description="Member to get the status histogram for",
            default=lambda ctx: ctx.author,
            displayed_default="You",
        ),
        after: str = commands.param(
            description="Time period to get the histogram for (from `time` to now)",
            default="1 week",
        ),
    ) -> None:
        try:
            after_dt = parse_time(after)
        except ValueError as err:
            msg = "Invalid time provided"
            raise ValueError(msg) from err

        after_dt.replace(tzinfo=None)

        activity = await self.bot.db_status.get(member.id)

        times = {
            "online": 0,
            "idle": 0,
            "dnd": 0,
            "offline": 0,
        }

        for entry in activity:
            times[entry["status_type"]] += (
                entry["end_time"] - entry["start_time"]
            ).total_seconds()

        total = sum(times.values())
        if total == 0:
            msg = "No activity data found"
            raise ValueError(msg)

        online_percent = times["online"] / total * 100
        idle_percent = times["idle"] / total * 100
        dnd_percent = times["dnd"] / total * 100
        offline_percent = times["offline"] / total * 100

        # create histogram
        tup = plt.subplots()
        fig: plt.Figure = tup[0]
        ax: plt.Axes = tup[1]
        ax.bar(
            ["Online", "Idle", "DnD", "Offline"],
            [online_percent, idle_percent, dnd_percent, offline_percent],
            color=[
                (174 / 255, 249 / 255, 184 / 255),
                (240 / 255, 247 / 255, 111 / 255),
                (244 / 255, 56 / 255, 56 / 255),
                (77 / 255, 78 / 255, 81 / 255),
            ],
        )

        ax.set_facecolor((0, 0, 0, 0))
        fig.set_facecolor((0, 0, 0, 0))

        ax.spines["top"].set_visible(False)

        ax.set_xlabel("Status")
        ax.set_ylabel("Percentage")

        ax.xaxis.label.set_fontsize(14)
        ax.yaxis.label.set_fontsize(14)

        ax.set_ylim(0, 100)

        ax.set_yticks(range(0, 101, 10))

        ax.spines["left"].set_linewidth(2)
        ax.spines["bottom"].set_linewidth(2)
        ax.spines["right"].set_linewidth(0)
        ax.spines["top"].set_linewidth(0)

        ax.tick_params(axis="both", which="major", labelsize=12)
        ax.tick_params(axis="both", which="minor", labelsize=10)

        ax.grid(color="grey", linestyle="--", linewidth=0.5)

        ax.set_xlabel("Status", color="white")
        ax.set_ylabel("Percentage", color="white")
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")
        ax.yaxis.label.set_color("white")
        ax.xaxis.label.set_color("white")

        ax.spines["bottom"].set_color("grey")
        ax.spines["left"].set_color("grey")
        ax.spines["bottom"].set_linestyle("--")
        ax.spines["left"].set_linestyle("--")

        ax.set_title(f"status distribution for {member.name}", color="white")
        ax.title.set_fontsize(18)

        # add percentages to the bars
        for i, (p, h) in enumerate(
            zip(
                [online_percent, idle_percent, dnd_percent, offline_percent],
                [times["online"], times["idle"], times["dnd"], times["offline"]],
            ),
        ):
            hours = int(h // 3600)  # convert to hours
            mins = round((h % 3600) / 60, 2)
            ax.text(
                i,
                p + 1,
                f"{p:.2f}% [{hours}h {mins}m]",
                ha="center",
                va="bottom",
                color="white",
            )

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)

        file = discord.File(buf, filename="histogram.png")
        embed = ctx.embed(title="Status Histogram")
        embed.set_image(url="attachment://histogram.png")

        await ctx.reply(file=file, embed=embed)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Status(bot))
