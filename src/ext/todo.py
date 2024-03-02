from datetime import datetime

import discord
from discord.ext import commands

from src.types.command import AutoTablePager, TaskIDConverter, VanirCog
from src.types.core import Vanir, VanirContext
from src.util.command import vanir_group


class Todo(VanirCog):
    """Keep track of what you need to get done"""

    emoji = "\N{Spiral Note Pad}"

    @vanir_group()
    async def todo(
        self, ctx: VanirContext, *, task: str = None, description: str = None
    ):
        if task is None:
            await ctx.invoke(self.get, True, False)  # type: ignore
        else:
            await ctx.invoke(self.add, task=task)  # type: ignore

    @todo.command(aliases=["new"])
    async def add(
        self,
        ctx: VanirContext,
        *,
        task: str = commands.param(description="The task to complete."),
    ):
        """Creates a new task. You can also use `\\todo <task>` as shorthand."""
        await self.bot.db_todo.create_todo(ctx.author.id, task)
        embed = ctx.embed(title=f"\N{White Heavy Check Mark} TODO: {task}")
        await ctx.reply(embed=embed, ephemeral=True)

    @todo.command(aliases=["all"])
    async def get(
        self,
        ctx: VanirContext,
        include_completed: bool = commands.param(
            description="Whether or not to include completed todos.", default=True
        ),
        completed_only: bool = commands.param(
            description="Whether or not to ONLY show completed todos.", default=False
        ),
    ):
        """Gets your current tasks. You can specify `include_completed` and `completed_only` to narrow."""
        results: list[dict[str, str | int]] = await self.bot.db_todo.get_all_todo(
            ctx.author.id, include_completed
        )
        if not results:
            embed = ctx.embed("You have no tasks. Use `\\todo <task>` to get started")
            await ctx.reply(embed=embed, ephemeral=True)
            return

        if completed_only:
            results = list(filter(lambda t: t["completed"], results))

        if not results:
            embed = ctx.embed(
                "No results matched your criteria", color=discord.Color.red()
            )
            await ctx.reply(embed=embed, ephemeral=True)
            return

        results_rows = [
            [
                r["title"],
                r["timestamp_created"].strftime("%Y/%m/%d"),
                r["completed"],
                r["todo_id"],
            ]
            for r in results
        ]

        results_rows.sort(key=lambda c: c[1])  # sort by date added

        view = AutoTablePager(
            self.bot,
            ctx.author,
            headers=["task", "created", "completed?", "id"],
            rows=results_rows,
            rows_per_page=3,
            include_hline=True,
        )
        embed = await view.update_embed()
        view.message = await ctx.reply(embed=embed, view=view, ephemeral=True)

    @todo.command(aliases=["finish", "done", "completed"])
    async def complete(
        self,
        ctx: VanirContext,
        *,
        todo: str = commands.param(
            description="The name or ID of the todo",
            default=None,
            displayed_default="<show all done todos>",
            converter=TaskIDConverter(),
        ),
    ):
        """Marks a task as done."""
        if todo is None:
            await ctx.invoke(self.get, completed_only=True)  # type: ignore
            return
        print(todo)
        changed = await self.bot.db_todo.complete_todo_by_id(ctx.author.id, int(todo))

        embed = ctx.embed(f"{changed['title']} Completed")
        await ctx.reply(embed=embed, ephemeral=True)

    @todo.command(aliases=["delete", "del", "d", "r"])
    async def remove(
        self,
        ctx: VanirContext,
        *,
        todo: str = commands.param(
            description="The task name or ID of what you want to remove",
            converter=TaskIDConverter(),
        ),
    ):
        """Completely removes a task from your list. You may want `\\todo done` instead."""
        removed = await self.bot.db_todo.remove_todo(ctx.author.id, int(todo))

        embed = ctx.embed(f"{removed['title']} removed")
        await ctx.reply(embed=embed, ephemeral=True)

    @todo.command()
    async def clear(self, ctx: VanirContext):
        """Removes all of your tasks. You may want `\\todo done <name>` or `\\todo remove <name>` instead."""
        removed = await self.bot.db_todo.clear(ctx.author.id)
        embed = ctx.embed(f"Removed {len(removed)} task{'s' if removed else ''}")
        await ctx.reply(embed=embed, ephemeral=True)


async def setup(bot: Vanir):
    await bot.add_cog(Todo(bot))
