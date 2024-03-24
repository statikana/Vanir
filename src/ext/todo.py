from inspect import Parameter

import discord
from discord.ext import commands
from discord.ui.button import Button

from src.types.command import (
    AutoTablePager,
    VanirCog,
    VanirView,
    vanir_group,
)
from src.types.core import Vanir, VanirContext
from src.types.database import TASK
from src.types.interface import TaskIDConverter
from src.util.command import safe_default
from src.util.parse import fuzzysearch
from src.util.ux import generate_modal


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
        task = await self.bot.db_todo.create(ctx.author.id, task)
        embed = ctx.embed(
            title=f"\N{WHITE HEAVY CHECK MARK} TODO: " f"{task['title']}",
            description=f"ID: `{task['todo_id']}`",
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

        results: list[TASK] = await self.bot.db_todo.get_by_user(
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

        embed, view = await create_task_gui(ctx, results)
        await view.update(update_content=False)
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

    @todo.command(aliases=["finish", "done", "completed"])
    async def complete(
        self,
        ctx: VanirContext,
        *,
        task: int = commands.param(
            description="The name or ID of the todo",
            default=None,
            displayed_default="<show all done todos>",
            converter=TaskIDConverter(required=False),
        ),
    ):
        """Marks a task as done."""
        if task is None or isinstance(task, Parameter):
            await ctx.invoke(self.get, include_completed=True, completed_only=True)  # type: ignore
            return

        changed = await self.bot.db_todo.complete_by_id(task)

        embed = ctx.embed(f"{changed['title']} Completed")
        await ctx.reply(embed=embed, view=AfterEdit(ctx), ephemeral=True)

    @todo.command(aliases=["delete", "del", "d", "r"])
    async def remove(
        self,
        ctx: VanirContext,
        *,
        task: int = commands.param(
            description="The task name or ID of what you want to remove",
            converter=TaskIDConverter(),
        ),
    ):
        """Completely removes a task from your list. You may want `\\todo done` instead."""
        removed = (await self.bot.db_todo.remove(task))[0]

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
        tasks = await self.bot.db_todo.get_by_user(
            ctx.author.id, include_completed=True
        )
        trimmed = fuzzysearch(query, tasks, key=lambda t: t["title"], threshold=30)

        embed, view = await create_task_gui(ctx, trimmed, autosort=False)
        await view.update(update_content=False)
        await ctx.reply(embed=embed, view=view)


async def create_task_gui(
    ctx: VanirContext,
    tasks: list[TASK],
    *,
    autosort: bool = True,
    start_page: int = 0,
) -> tuple[discord.Embed, "TaskPager"]:
    if autosort:
        tasks.sort(
            key=lambda c: (c["completed"], c["timestamp_created"])
        )  # sort by completed?, date added

    view = TaskPager(
        ctx,
        headers=["task", "done?", "created", "id"],
        tasks=tasks,
        rows_per_page=10,
        include_hline=True,
        start_page=start_page,
    )

    return await view.update_embed(), view


class TaskPager(AutoTablePager):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        headers: list[str],
        tasks: list[TASK],
        rows_per_page: int,
        dtypes: list[str] = None,
        data_name: str = None,
        include_hline: bool = False,
        start_page: int = 0,
    ):
        super().__init__(
            bot=ctx.bot,
            user=ctx.author,
            headers=headers,
            rows=tasks,
            rows_per_page=rows_per_page,
            dtypes=dtypes,
            data_name=data_name,
            include_hline=include_hline,
            row_key=lambda task: list(task.values())[1:],
            start_page=start_page,
        )
        self.ctx = ctx

        self.add_todo = AddTodoButton(self.ctx, all=self.rows)
        self.finish_todo = FinishTodoButton(
            self.ctx, all=self.rows, options=self.current, current_page=self.page
        )
        self.remove_todo = RemoveTodoButton(
            self.ctx, all=self.rows, options=self.current, current_page=self.page
        )
        self.add_item(self.add_todo)
        self.add_item(self.finish_todo)
        self.add_item(self.remove_todo)

    async def update(
        self,
        itx: discord.Interaction = None,
        source_button: Button = None,
        update_content: bool = True,
    ):
        self.finish_todo.options = self.current
        self.remove_todo.options = self.current
        self.finish_todo.current_page = self.page
        self.remove_todo.current_page = self.page
        await super().update(itx, source_button, update_content)


class AddTodoButton(discord.ui.Button["TaskPager"]):
    def __init__(self, ctx: VanirContext, *, all: list[TASK]):
        super().__init__(
            style=discord.ButtonStyle.primary, emoji="\N{HEAVY PLUS SIGN}", label="New"
        )
        self.ctx = ctx
        self.all = all

    async def callback(self, itx: discord.Interaction):
        task, *_ = await generate_modal(
            itx,
            title="Add a new task",
            fields=[
                discord.ui.TextInput(
                    style=discord.TextStyle.paragraph,
                    label="Task",
                    placeholder="What do you need to do?",
                    required=True,
                )
            ],
        )
        task = await self.ctx.bot.db_todo.create(self.ctx.author.id, task)
        new_tasks = [task] + self.all
        embed, view = await create_task_gui(
            ctx=self.ctx, tasks=new_tasks, autosort=False, start_page=self.view.page
        )
        await view.update(itx, update_content=False)
        await itx.message.edit(embed=embed, view=view)


class FinishTodoButton(discord.ui.Button["TaskPager"]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all: list[TASK],
        options: list[TASK],
        current_page: int,
    ):
        super().__init__(
            style=discord.ButtonStyle.success,
            emoji="\N{HEAVY CHECK MARK}",
            label="Done",
        )
        self.ctx = ctx
        self.all = all
        self.options = options
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction):
        embed = self.ctx.embed("Select the tasks you want to mark as done or not done")
        view = VanirView(self.ctx.bot, user=self.ctx.author)
        view.add_item(
            FinishTodoDetachment(
                self.ctx,
                all=self.all,
                options=self.options,
                source=itx.message,
                current_page=self.current_page,
            )
        )
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


class FinishTodoDetachment(discord.ui.Select[VanirView]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all: list,
        options: list,
        source: discord.Message,
        current_page: int,
    ):
        select_options = [
            discord.SelectOption(
                label=task["title"][:100],
                value=task["todo_id"],
                default=task["completed"],
            )
            for task in options
        ]
        super().__init__(
            placeholder="Mark tasks as done...",
            options=select_options,
            max_values=len(select_options),
            row=0,
        )
        self.ctx = ctx
        self.all = all
        self.source = source
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction):
        await itx.response.defer()
        all_set = set(int(opt.value) for opt in self.options)

        mark_as_done = set(int(v) for v in self.values)
        mark_as_not_done = all_set - mark_as_done

        await self.ctx.bot.db_todo.complete_by_id(*mark_as_done)
        await self.ctx.bot.db_todo.uncomplete_by_id(*mark_as_not_done)

        new_tasks = [dict(task) for task in self.all]
        for task in new_tasks:
            if task["todo_id"] in mark_as_done:
                task["completed"] = True
            elif task["todo_id"] in mark_as_not_done:
                task["completed"] = False

        embed, view = await create_task_gui(
            ctx=self.ctx, tasks=new_tasks, autosort=False, start_page=self.current_page
        )
        await view.update(itx, update_content=False)
        await self.source.edit(embed=embed, view=view)


class RemoveTodoButton(discord.ui.Button["TaskPager"]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all: list[TASK],
        options: list[TASK],
        current_page: int,
    ):
        super().__init__(
            style=discord.ButtonStyle.danger,
            emoji="\N{HEAVY MULTIPLICATION X}",
            label="Remove",
        )
        self.ctx = ctx
        self.all = all
        self.options = options
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction):
        embed = self.ctx.embed("Select the tasks you want to remove")
        view = VanirView(self.ctx.bot, user=self.ctx.author)

        view.add_item(
            RemoveTodoDetachment(
                self.ctx,
                all=self.all,
                options=self.options,
                source=itx.message,
                current_page=self.current_page,
            )
        )

        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


class RemoveTodoDetachment(discord.ui.Select[VanirView]):
    # include page num in __init__
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all: list,
        options: list,
        source: discord.Message,
        current_page: int,
    ):
        select_options = [
            discord.SelectOption(
                label=task["title"][:100],
                value=task["todo_id"],
            )
            for task in options
        ]
        super().__init__(
            placeholder="Select tasks to remove...",
            options=select_options,
            max_values=len(select_options),
        )
        self.ctx = ctx
        self.all = all
        self.source = source
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction):
        await itx.response.defer()
        removed = set(int(v) for v in self.values)
        await self.ctx.bot.db_todo.remove(*removed)

        new_tasks = [dict(task) for task in self.all if task["todo_id"] not in removed]
        embed, view = await create_task_gui(
            ctx=self.ctx, tasks=new_tasks, autosort=False, start_page=self.current_page
        )
        await view.update(itx, update_content=False)
        await self.source.edit(embed=embed, view=view)


class AfterEdit(VanirView):
    def __init__(self, ctx: VanirContext):
        super().__init__(bot=ctx.bot, user=ctx.author)
        self.ctx = ctx

    @discord.ui.button(
        label="See Tasks",
        emoji="\N{SPIRAL NOTE PAD}",
        style=discord.ButtonStyle.primary,
    )
    async def see_tasks(self, itx: discord.Interaction, button: discord.ui.Button):
        user_tasks = await self.bot.db_todo.get_by_user(self.ctx.author.id)
        embed, view = await create_task_gui(
            ctx=self.ctx, tasks=user_tasks, autosort=True
        )
        await view.update(update_content=False)
        await itx.response.edit_message(embed=embed, view=view)


async def setup(bot: Vanir):
    await bot.add_cog(Todo(bot))
