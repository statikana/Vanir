from __future__ import annotations

import io
from inspect import Parameter
from typing import TYPE_CHECKING

import dataframe_image as dfi
import discord
import pandas as pd
from discord.ext import commands

from src.types.command import (
    AutoTablePager,
    VanirCog,
    VanirView,
    vanir_group,
)
from src.types.interface import TaskIDConverter
from src.util.command import safe_default
from src.util.format import wrap_text
from src.util.parse import fuzzysearch
from src.util.ux import generate_modal

if TYPE_CHECKING:
    from discord.ui.button import Button

    from src.types.core import Vanir, VanirContext
    from src.types.orm import TASK


class Todo(VanirCog):
    """Keep track of what you need to get done."""

    emoji = "\N{SPIRAL NOTE PAD}"

    @vanir_group()
    async def todo(self, ctx: VanirContext, *, task: str | None = None) -> None:
        r"""Get your todo list [default: `\todo get` or `\todo add <task>`]."""
        if task is None:
            await ctx.invoke(self.get, True, False)
        else:
            await ctx.invoke(self.add, task=task)

    @todo.command(aliases=["new"])
    async def add(
        self,
        ctx: VanirContext,
        *,
        task: str = commands.param(description="The task to complete."),
    ) -> None:
        r"""Create a new task. You can also use `\todo <task>` as shorthand."""
        task = await self.bot.db_todo.create(ctx.author.id, task)
        embed = ctx.embed(
            title=f"\N{WHITE HEAVY CHECK MARK} TODO: {task['title']}",
            description=f"ID: `{task['todo_id']}`",
        )
        await ctx.reply(embed=embed, view=AfterEdit(ctx), ephemeral=True)

    @todo.command(aliases=["all"])
    async def get(
        self,
        ctx: VanirContext,
        include_completed: bool = commands.param(
            description="Whether or not to include completed todos.",
            default=True,
        ),
        completed_only: bool = commands.param(
            description="Whether or not to ONLY show completed todos.",
            default=False,
        ),
    ) -> None:
        """Gets your current tasks. You can specify `include_completed` and `completed_only` to narrow."""
        include_completed = safe_default(include_completed)
        completed_only = safe_default(completed_only)

        results: list[TASK] = await self.bot.db_todo.get_by_user(
            ctx.author.id,
            include_completed=include_completed,
        )

        if not results:
            embed = ctx.embed("You have no tasks. Use `+todo <task>` to get started")
            await ctx.reply(embed=embed, ephemeral=True)
            return

        if completed_only:
            results = list(filter(lambda t: t["completed"], results))

        if not results:
            embed = ctx.embed(
                "No results matched your criteria",
                color=discord.Color.red(),
            )
            await ctx.reply(embed=embed, ephemeral=True)
            return

        embed, file, view = await create_task_gui(ctx, results)
        await view.update(update_content=False)
        message = await ctx.reply(embed=embed, file=file, view=view)
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
    ) -> None:
        """Mark a task as done."""
        if task is None or isinstance(task, Parameter):
            await ctx.invoke(self.get, include_completed=True, completed_only=True)
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
    ) -> None:
        r"""Completely removes a task from your list. You may want `\todo done` instead."""
        removed = (await self.bot.db_todo.remove(task))[0]

        embed = ctx.embed(f"{removed['title']} removed")
        await ctx.reply(embed=embed, view=AfterEdit(ctx), ephemeral=True)

    @todo.command()
    async def clear(self, ctx: VanirContext) -> None:
        r"""Removes all of your tasks. You may want `\todo done <name>` or `\todo remove <name>` instead."""
        removed = await self.bot.db_todo.clear(ctx.author.id)
        embed = ctx.embed(f"Removed {len(removed)} task{'s' if removed else ''}")
        await ctx.reply(embed=embed, ephemeral=True)

    @todo.command()
    async def search(self, ctx: VanirContext, query: str) -> None:
        """Search your tasks for a specific query."""
        tasks = await self.bot.db_todo.get_by_user(
            ctx.author.id,
            include_completed=True,
        )
        trimmed = fuzzysearch(query, tasks, key=lambda t: t["title"], threshold=30)

        embed, file, view = await create_task_gui(ctx, trimmed, autosort=False)
        await view.update(update_content=False)
        await ctx.reply(embed=embed, file=file, view=view)


async def create_task_gui(
    ctx: VanirContext,
    tasks: list[TASK],
    *,
    autosort: bool = True,
    start_page: int = 0,
) -> tuple[discord.Embed, discord.File, TaskPager]:
    if autosort:
        tasks.sort(
            key=lambda c: (c["completed"], c["timestamp_created"]),
        )  # sort by completed?, date added

    view = TaskPager(
        ctx,
        headers=["task", "done?", "created", "id"],
        tasks=tasks,
        rows_per_page=10,
        include_hline=True,
        start_page=start_page,
    )

    return *(await view.update_embed()), view


class TaskPager(AutoTablePager):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        headers: list[str],
        tasks: list[TASK],
        rows_per_page: int,
        dtypes: list[str] | None = None,
        data_name: str | None = None,
        include_hline: bool = False,
        start_page: int = 0,
    ) -> None:
        super().__init__(
            bot=ctx.bot,
            user=ctx.author,
            headers=headers,
            rows=tasks,
            rows_per_page=rows_per_page,
            dtypes=dtypes,
            data_name=data_name,
            include_hline=include_hline,
            row_key=format_task_row,
            start_page=start_page,
            include_spacer_image=True,
        )
        self.ctx = ctx

        self.add_todo = AddTodoButton(self.ctx, all_tasks=self.rows)
        self.finish_todo = FinishTodoButton(
            self.ctx,
            all_tasks=self.rows,
            options=self.current,
            current_page=self.page,
        )
        self.remove_todo = RemoveTodoButton(
            self.ctx,
            all_tasks=self.rows,
            options=self.current,
            current_page=self.page,
        )
        self.edit_todo = EditTodoButton(
            self.ctx,
            all_tasks=self.rows,
            options=self.current,
            current_page=self.page,
        )
        self.add_item(self.add_todo)
        self.add_item(self.finish_todo)
        self.add_item(self.remove_todo)
        self.add_item(self.edit_todo)

    async def update(
        self,
        itx: discord.Interaction = None,
        source_button: Button = None,
        update_content: bool = True,
    ) -> None:
        self.finish_todo.options = self.current
        self.remove_todo.options = self.current
        self.edit_todo.options = self.current
        self.finish_todo.current_page = self.page
        self.remove_todo.current_page = self.page
        self.edit_todo.current_page = self.page
        embed, file = await self.update_embed()

        await super().update(itx, source_button, update_content=False)

        if update_content and not itx.response.is_done():
            embed.description = None
            await itx.response.edit_message(embed=embed, attachments=[file], view=self)

    async def update_embed(self) -> tuple[discord.Embed, discord.File]:
        data: list[TASK] = self.current
        fmted = [format_task_row(task) for task in data]
        todo_df = (
            pd.DataFrame(
                data=fmted,
                columns=self.headers,
            )
            .style.apply(
                lambda done: [f"color: {"green" if v else "red"};" for v in done],
                subset=["done?"],
            )
            .format_index(lambda _: "")
            .set_properties(
                **{
                    "text-align": "left",
                    "border-collapse": "collapse",
                },
            )
            .set_table_styles(
                [
                    {"selector": "th", "props": [("text-align", "left")]},
                ],
            )
        )
        # col header align

        buffer = io.BytesIO()
        dfi.export(todo_df, buffer)
        buffer.seek(0)

        embed = self.ctx.embed()
        file = discord.File(buffer, filename="tasks.png")
        embed.set_image(url="attachment://tasks.png")
        return embed, file


class AddTodoButton(discord.ui.Button["TaskPager"]):
    def __init__(self, ctx: VanirContext, *, all_tasks: list[TASK]) -> None:
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="\N{HEAVY PLUS SIGN}",
            label="New",
        )
        self.ctx = ctx
        self.all = all_tasks

    async def callback(self, itx: discord.Interaction) -> None:
        task, *_ = await generate_modal(
            itx,
            title="Add a new task",
            fields=[
                discord.ui.TextInput(
                    style=discord.TextStyle.paragraph,
                    label="Task",
                    placeholder="What do you need to do?",
                    required=True,
                ),
            ],
        )
        task = await self.ctx.bot.db_todo.create(self.ctx.author.id, task)
        new_tasks = [task, *self.all]
        embed, file, view = await create_task_gui(
            ctx=self.ctx,
            tasks=new_tasks,
            autosort=False,
            start_page=self.view.page,
        )
        await view.update(itx, update_content=False)
        await itx.message.edit(embed=embed, attachments=[file], view=view)


class FinishTodoButton(discord.ui.Button["TaskPager"]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all_tasks: list[TASK],
        options: list[TASK],
        current_page: int,
    ) -> None:
        super().__init__(
            style=discord.ButtonStyle.success,
            emoji="\N{HEAVY CHECK MARK}",
            label="Done",
        )
        self.ctx = ctx
        self.all = all_tasks
        self.options = options
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction) -> None:
        embed = self.ctx.embed("Select the tasks you want to mark as done or not done")
        view = VanirView(self.ctx.bot, user=self.ctx.author)
        view.add_item(
            FinishTodoDetachment(
                self.ctx,
                all_tasks=self.all,
                options=self.options,
                source=itx.message,
                current_page=self.current_page,
            ),
        )
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


class FinishTodoDetachment(discord.ui.Select[VanirView]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all_tasks: list,
        options: list,
        source: discord.Message,
        current_page: int,
    ) -> None:
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
        self.all = all_tasks
        self.source = source
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction) -> None:
        await itx.response.defer()
        all_set = {int(opt.value) for opt in self.options}

        mark_as_done = {int(v) for v in self.values}
        mark_as_not_done = all_set - mark_as_done

        await self.ctx.bot.db_todo.complete_by_id(*mark_as_done)
        await self.ctx.bot.db_todo.uncomplete_by_id(*mark_as_not_done)

        new_tasks = [dict(task) for task in self.all]
        for task in new_tasks:
            if task["todo_id"] in mark_as_done:
                task["completed"] = True
            elif task["todo_id"] in mark_as_not_done:
                task["completed"] = False

        embed, file, view = await create_task_gui(
            ctx=self.ctx,
            tasks=new_tasks,
            autosort=False,
            start_page=self.current_page,
        )
        await view.update(itx, update_content=False)
        await self.source.edit(embed=embed, attachments=[file], view=view)


class RemoveTodoButton(discord.ui.Button["TaskPager"]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all_tasks: list[TASK],
        options: list[TASK],
        current_page: int,
    ) -> None:
        super().__init__(
            style=discord.ButtonStyle.danger,
            emoji="\N{HEAVY MULTIPLICATION X}",
            label="Remove",
        )
        self.ctx = ctx
        self.all = all_tasks
        self.options = options
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction) -> None:
        embed = self.ctx.embed("Select the tasks you want to remove")
        view = VanirView(self.ctx.bot, user=self.ctx.author)

        view.add_item(
            RemoveTodoDetachment(
                self.ctx,
                all_tasks=self.all,
                options=self.options,
                source=itx.message,
                current_page=self.current_page,
            ),
        )

        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


class RemoveTodoDetachment(discord.ui.Select[VanirView]):
    # include page num in __init__
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all_tasks: list,
        options: list,
        source: discord.Message,
        current_page: int,
    ) -> None:
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
        self.all = all_tasks
        self.source = source
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction) -> None:
        await itx.response.defer()
        removed = {int(v) for v in self.values}
        await self.ctx.bot.db_todo.remove(*removed)

        new_tasks = [dict(task) for task in self.all if task["todo_id"] not in removed]
        embed, file, view = await create_task_gui(
            ctx=self.ctx,
            tasks=new_tasks,
            autosort=False,
            start_page=self.current_page,
        )
        await view.update(itx, update_content=False)
        await self.source.edit(embed=embed, attachments=[file], view=view)


class EditTodoButton(discord.ui.Button["TaskPager"]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all_tasks: list[TASK],
        options: list[TASK],
        current_page: int,
    ) -> None:
        super().__init__(
            style=discord.ButtonStyle.secondary,
            emoji="\N{PENCIL}",
            label="Edit",
        )
        self.ctx = ctx
        self.all = all_tasks
        self.options = options
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction) -> None:
        embed = self.ctx.embed("Select the task you want to edit")
        view = VanirView(self.ctx.bot, user=self.ctx.author)
        view.add_item(
            EditTodoDetachment(
                self.ctx,
                all_tasks=self.all,
                options=self.options,
                source=itx.message,
                current_page=self.current_page,
            ),
        )
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


class EditTodoDetachment(discord.ui.Select[VanirView]):
    def __init__(
        self,
        ctx: VanirContext,
        *,
        all_tasks: list,
        options: list,
        source: discord.Message,
        current_page: int,
    ) -> None:
        select_options = [
            discord.SelectOption(
                label=task["title"][:100],
                value=task["todo_id"],
            )
            for task in options
        ]
        super().__init__(
            placeholder="Select task to edit...",
            options=select_options,
            max_values=1,
        )
        self.ctx = ctx
        self.all = all_tasks
        self.source = source
        self.current_page = current_page

    async def callback(self, itx: discord.Interaction) -> None:
        task_id = int(self.values[0])
        task = next(t for t in self.all if t["todo_id"] == task_id)

        task, *_ = await generate_modal(
            itx,
            title="Edit a task",
            fields=[
                discord.ui.TextInput(
                    style=discord.TextStyle.paragraph,
                    label="Task",
                    placeholder="What do you need to do?",
                    default=task["title"],
                    required=True,
                ),
            ],
        )
        await self.ctx.bot.db_todo.edit(task_id, task)

        new_tasks = [dict(task) for task in self.all]
        for to_up_task in new_tasks:
            if to_up_task["todo_id"] == task_id:
                to_up_task["title"] = task

        embed, file, view = await create_task_gui(
            ctx=self.ctx,
            tasks=new_tasks,
            autosort=False,
            start_page=self.current_page,
        )
        await view.update(itx, update_content=False)
        await self.source.edit(embed=embed, attachments=[file], view=view)


class AfterEdit(VanirView):
    def __init__(self, ctx: VanirContext) -> None:
        super().__init__(bot=ctx.bot, user=ctx.author)
        self.ctx = ctx

    @discord.ui.button(
        label="See Tasks",
        emoji="\N{SPIRAL NOTE PAD}",
        style=discord.ButtonStyle.primary,
    )
    async def see_tasks(
        self,
        itx: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        user_tasks = await self.bot.db_todo.get_by_user(
            self.ctx.author.id,
            include_completed=True,
        )
        embed, file, view = await create_task_gui(
            ctx=self.ctx,
            tasks=user_tasks,
            autosort=True,
        )
        await view.update(update_content=False)
        await itx.response.edit_message(embed=embed, attachments=[file], view=view)


def format_task_row(task: TASK) -> list[str]:
    title = wrap_text(task["title"], 40, "<br> ")
    completed = task["completed"]
    timestamp = f"{task['timestamp_created']:%x}"
    todo_id = str(task["todo_id"])
    return [
        title,
        completed,
        timestamp,
        todo_id,
    ]


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Todo(bot))
