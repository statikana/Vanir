import asyncpg
import discord
from discord.ext import commands

from src.types.command import AutoTablePager, TaskIDConverter, VanirCog
from src.types.core import Vanir, VanirContext
from src.util.command import vanir_group
from src.util.parse import fuzzysearch


class Todo(VanirCog):
    """Keep track of what you need to get done"""

    emoji = "\N{Spiral Note Pad}"

    @vanir_group()
    async def todo(self, ctx: VanirContext, *, task: str = None):
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
        todo = await self.bot.db_todo.create_todo(ctx.author.id, task)
        embed = ctx.embed(
            title=f"\N{White Heavy Check Mark} TODO: " f"{todo['title']}",
            description=f"ID: `{todo['todo_id']}`",
        )
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
        results: list[asyncpg.Record] = await self.bot.db_todo.get_all_todo(
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

        await self.show_todos(ctx, results)

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

    @todo.command()
    async def search(self, ctx: VanirContext, query: str):
        todos = await self.bot.db_todo.get_all_todo(
            ctx.author.id, include_completed=True
        )
        trimmed = fuzzysearch(query, todos, key=lambda t: t["title"], threshold=30)
        await self.show_todos(ctx, trimmed, autosort=False)

    async def show_todos(
        self,
        ctx: VanirContext,
        todos: list[asyncpg.Record],
        *,
        autosort: bool = True,
        as_image: bool = True,
    ):

        results_rows = [
            [
                t["title"],
                t["timestamp_created"].strftime("%Y/%m/%d"),
                t["completed"],
                t["todo_id"],
            ]
            for t in todos
        ]
        if autosort:
            results_rows.sort(
                key=lambda c: (c[2], c[1])
            )  # sort by completed?, date added

        view = AutoTablePager(
            self.bot,
            ctx.author,
            headers=["task", "created", "done?", "id"],
            rows=results_rows,
            rows_per_page=10,
            include_hline=True,
        )
        if as_image:
            embed, file = await view.update_embed()
            await view.update(update_content=False)
            view.message = await ctx.reply(embed=embed, view=view, files=[file])
        else:
            embed = await view.update_embed()
            await view.update(update_content=False)
            view.message = await ctx.reply(embed=embed, view=view)  # type: ignore


async def setup(bot: Vanir):
    await bot.add_cog(Todo(bot))
