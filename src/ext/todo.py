from inspect import Parameter

import asyncpg
import discord
from discord.ext import commands
from discord.ui.button import Button

from src.types.command import (
    AutoTablePager,
    VanirCog,
    VanirPagerT,
    VanirView,
    vanir_group,
)
from src.types.core import Vanir, VanirContext
from src.types.interface import TaskIDConverter
from src.util.command import safe_default
from src.util.parse import fuzzysearch


class Todo(VanirCog):
    """Keep track of what you need to get done"""

    emoji = "\N{SPIRAL NOTE PAD}"

    @vanir_group()
    async def todo(self, ctx: VanirContext, *, task: str = None):
        """Get your todo list [default: `\\todo get` or `\\todo add <task>`]"""
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
        include_completed = safe_default(include_completed)
        completed_only = safe_default(completed_only)

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
        message = await ctx.reply(embed=embed, view=view, file=file)
        view.message = message

    @todo.command(aliases=["finish", "done", "completed"])
    async def complete(
        self,
        ctx: VanirContext,
        *,
        todo: int = commands.param(
            description="The name or ID of the todo",
            default=None,
            displayed_default="<show all done todos>",
            converter=TaskIDConverter(required=False),
        ),
    ):
        """Marks a task as done."""
        if todo is None or isinstance(todo, Parameter):
            await ctx.invoke(self.get, include_completed=True, completed_only=True)  # type: ignore
            return

        changed = await self.bot.db_todo.complete_by_id(todo)

        embed = ctx.embed(f"{changed['title']} Completed")
        await ctx.reply(embed=embed, view=AfterEdit(ctx), ephemeral=True)

    @todo.command(aliases=["delete", "del", "d", "r"])
    async def remove(
        self,
        ctx: VanirContext,
        *,
        todo: int = commands.param(
            description="The task name or ID of what you want to remove",
            converter=TaskIDConverter(),
        ),
    ):
        """Completely removes a task from your list. You may want `\\todo done` instead."""
        removed = await self.bot.db_todo.remove(todo)

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
    todos: list[asyncpg.Record | list[list[str | int | bool]]],
    *,
    autosort: bool = True,
    as_image: bool = False,
) -> tuple[discord.Embed, discord.File, "TodoPager"]:
    try:
        results_rows = [
            [
                t["title"],
                t["timestamp_created"].strftime("%Y/%m/%d"),
                t["completed"],
                t["todo_id"],
            ]
            for t in todos
        ]
    except TypeError:
        results_rows = todos
    if autosort:
        results_rows.sort(key=lambda c: (c[2], c[1]))  # sort by completed?, date added

    view = TodoPager(
        ctx,
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
        ctx: VanirContext,
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
            bot=ctx.bot,
            user=ctx.author,
            as_image=as_image,
            headers=headers,
            rows=rows,
            rows_per_page=rows_per_page,
            dtypes=dtypes,
            data_name=data_name,
            include_hline=include_hline,
        )
        self.ctx = ctx
        prev = self.children
        for child in prev:
            self.remove_item(child)

        self.add_item(
            MarkTodoAsDone(
                ctx=self.ctx,
                all=rows,
                options=rows[
                    self.cur_page * rows_per_page : (self.cur_page + 1)
                    * rows_per_page
                ],
            )
        )

        for child in prev:
            child.row = None
            self.add_item(child)
        
    async def update(self, itx: discord.Interaction = None, source_button: Button = None, update_content: bool = True):
        done_selector: MarkTodoAsDone = discord.utils.get(self.children, custom_id="mark_todo_as_done")
        if done_selector is None:
            return
        done_selector.options = [
            discord.SelectOption(label=todo[0][:100], value=todo[3], default=todo[2])
            for todo in self.rows[self.cur_page * self.items_per_page : (self.cur_page + 1) * self.items_per_page]
        ]
        done_selector.max_values = len(done_selector.options)
        for opt in done_selector.options:
            opt.default = discord.utils.find(lambda r: r[3]==opt.value, self.rows)[2]
            
        await super().update(itx, source_button, update_content)
        


class MarkTodoAsDone(discord.ui.Select[TodoPager]):
    def __init__(self, ctx: VanirContext, all: list, options: list):
        select_options = [
            discord.SelectOption(label=todo[0][:100], value=todo[3], default=todo[2])
            for todo in options
        ]
        super().__init__(
            placeholder="Mark tasks as done...",
            options=select_options,
            max_values=len(select_options),
            row=0,
            custom_id="mark_todo_as_done",
        )
        self.ctx = ctx
        self.all = all

    async def callback(self, itx: discord.Interaction):
        all_set = set(int(opt.value) for opt in self.options)
        
        mark_as_done = set(int(v) for v in self.values)
        mark_as_not_done = all_set - mark_as_done
        
        await self.ctx.bot.db_todo.complete_by_id(*mark_as_done)
        await self.ctx.bot.db_todo.uncomplete_by_id(*mark_as_not_done)

        for todo in self.all:
            if todo[3] in mark_as_done:
                todo[2] = True
            elif todo[3] in mark_as_not_done:
                todo[2] = False
                
        embed, file, view = await create_todo_gui(
            ctx=self.ctx, todos=self.all, autosort=False
        )
        view.cur_page = self.view.cur_page
        await view.update(itx, update_content=False)
        await itx.response.edit_message(
            embed=embed, view=view, attachments=[file] if file else []
        )


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
        await view.update(itx, update_content=False)
        await itx.response.edit_message(
            embed=embed, view=view, attachments=[file] if file else []
        )


async def setup(bot: Vanir):
    await bot.add_cog(Todo(bot))
