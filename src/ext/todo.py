import asyncpg
import discord
from discord.ext import commands

from src.types.command import (
    AutoTablePager,
    TaskIDConverter,
    VanirCog,
    VanirPagerT,
    VanirView,
    vanir_group,
)
from src.types.core import Vanir, VanirContext
from src.util.parse import fuzzysearch


class Todo(VanirCog):
    """Keep track of what you need to get done"""

    emoji = "\N{SPIRAL NOTE PAD}"

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
        todo = await self.bot.db_todo.create(ctx.author.id, task)
        embed = ctx.embed(
            title=f"\N{WHITE HEAVY CHECK MARK} TODO: " f"{todo['title']}",
            description=f"ID: `{todo['todo_id']}`",
        )
        await ctx.reply(embed=embed, view=AfterEdit(ctx), ephemeral=True)

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
        results: list[asyncpg.Record] = await self.bot.db_todo.get_by_user(
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

        embed, file, view = await create_todo_gui(ctx, results, as_image=False)
        await view.update(update_content=False)
        await ctx.reply(embed=embed, view=view, file=file)

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
        changed = await self.bot.db_todo.complete_by_id(int(todo))

        embed = ctx.embed(f"{changed['title']} Completed")
        await ctx.reply(embed=embed, view=AfterEdit(ctx), ephemeral=True)

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
        removed = await self.bot.db_todo.remove(int(todo))

        embed = ctx.embed(f"{removed['title']} removed")
        await ctx.reply(embed=embed, view=AfterEdit(ctx), ephemeral=True)

    @todo.command()
    async def clear(self, ctx: VanirContext):
        """Removes all of your tasks. You may want `\\todo done <name>` or `\\todo remove <name>` instead."""
        removed = await self.bot.db_todo.clear(ctx.author.id)
        embed = ctx.embed(f"Removed {len(removed)} task{'s' if removed else ''}")
        await ctx.reply(embed=embed, ephemeral=True)

    @todo.command()
    async def search(self, ctx: VanirContext, query: str):
        """Searches your tasks for a specific query."""
        todos = await self.bot.db_todo.get_by_user(
            ctx.author.id, include_completed=True
        )
        trimmed = fuzzysearch(query, todos, key=lambda t: t["title"], threshold=30)

        embed, file, view = await create_todo_gui(ctx, trimmed, autosort=False)
        await view.update(update_content=False)
        await ctx.reply(embed=embed, view=view, file=file)


async def create_todo_gui(
    ctx: VanirContext,
    todos: list[asyncpg.Record],
    *,
    autosort: bool = True,
    as_image: bool = False,
) -> tuple[discord.Embed, discord.File, discord.ui.View]:
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
        results_rows.sort(key=lambda c: (c[2], c[1]))  # sort by completed?, date added

    view = AutoTablePager(
        ctx.bot,
        ctx.author,
        headers=["task", "created", "done?", "id"],
        rows=results_rows,
        as_image=as_image,
        rows_per_page=10,
        include_hline=True,
    )

    return *(await view.update_embed()), view


class TodoPager(AutoTablePager):
    def __init__(
        self,
        bot: Vanir,
        user: discord.User,
        *,
        as_image: bool = True,
        headers: list[str],
        rows: list[VanirPagerT],
        rows_per_page: int,
        dtypes: list[str] = None,
        data_name: str = None,
        include_hline: bool = False,
    ):
        super().__init__(
            bot,
            user,
            as_image=as_image,
            headers=headers,
            rows=rows,
            rows_per_page=rows_per_page,
            dtypes=dtypes,
            data_name=data_name,
            include_hline=include_hline,
        )

        for child in self.children:
            child.row += 2


class MarkTodoAsDone(discord.ui.Select):
    def __init__(self, options: list[tuple[str, int]]):
        super().__init__(
            placeholder="Mark tasks as DONE",
            options=[
                discord.SelectOption(label=todo_label[:100], value=todo_id)
                for todo_label, todo_id in options
            ],
            max_values=25,
        )

    async def callback(self, itx: discord.Interaction):
        view = self.view
        if not isinstance(view, AutoTablePager):
            raise RuntimeError

        view.items

        await itx.response.edit_message()


class AfterEdit(VanirView):
    def __init__(self, ctx: VanirContext):
        super().__init__(bot=ctx.bot, user=ctx.author)
        self.ctx = ctx

    @discord.ui.button(
        label="View TODO",
        style=discord.ButtonStyle.primary,
        emoji="\N{SPIRAL NOTE PAD}",
    )
    async def view_todo(self, itx: discord.Interaction, button: discord.ui.Button):
        embed, file, view = await create_todo_gui(
            ctx=self.ctx,
            todos=await self.ctx.bot.db_todo.get_by_user(
                itx.user.id, include_completed=True
            ),
        )
        await itx.response.edit_message(
            embed=embed, view=view, attachments=[file] if file else []
        )


async def setup(bot: Vanir):
    await bot.add_cog(Todo(bot))
