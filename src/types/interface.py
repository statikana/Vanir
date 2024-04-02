from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from src.types.command import BotObjectT
from src.util.regex import EMOJI_REGEX

if TYPE_CHECKING:
    import re

    from src.types.core import VanirContext


class MessageSearchConverter(commands.Converter[str]):
    def __init__(
        self,
        *,
        regex: re.Pattern,
        n_lim: int = -1,
        use_reference: bool = True,
        history_lim: int = 10,
    ) -> None:
        """
        Convert regex pattern in messages.

        Args:
        ----
            regex (re.Pattern): The regex pattern to search for.
            n_lim (int, optional): The maximum number of results to find. Defaults to -1, meaning no limit.
            use_reference (bool, optional): Whether to search the message that was replied to. Defaults to True.
            history_lim (int, optional): The maximum number of messages to search in the channel history. Defaults to 10.

        """
        self.regex = regex
        self.n_to_find = n_lim
        self.use_reference = use_reference
        self.history_lim = history_lim

    async def convert(self, ctx: commands.Context, argument: str) -> list[str]:
        found = []
        results = self.regex.findall(argument)
        found.extend(results)

        if self.n_to_find != -1 and len(found) >= self.n_to_find:
            return found[: self.n_to_find]

        if self.use_reference and ctx.message.reference is not None:
            message = await ctx.fetch_message(ctx.message.reference.message_id)
            results = self.regex.findall(message.content)
            found.extend(results)

        if self.n_to_find != -1 and len(found) >= self.n_to_find:
            return found[: self.n_to_find]

        if self.history_lim != -1:
            async for message in ctx.channel.history(limit=self.history_lim):
                results = self.regex.findall(message.content)
                found.extend(results)

                if self.n_to_find != -1 and len(found) >= self.n_to_find:
                    return found[: self.n_to_find]

        return found[: self.n_to_find]


class BotObjectConverter(commands.Converter[BotObjectT]):
    async def convert(self, ctx: VanirContext, argument: str) -> BotObjectT:
        cmd = ctx.bot.get_command(argument.lower())
        if cmd is not None:
            return cmd
        cog = discord.utils.find(
            lambda c: c.qualified_name.casefold() == argument.casefold(),
            ctx.bot.cogs.values(),
        )
        if cog is not None:
            return cog
        return None


class TaskIDConverter(commands.Converter[int]):
    def __init__(self, required: bool = True) -> None:
        self.required = required

    async def convert(self, ctx: VanirContext, argument: str) -> int:
        if argument.isdigit():
            todo = await ctx.bot.db_todo.get_by_id(int(argument))
            if todo is not None:
                return int(argument)

        task = await ctx.bot.db_todo.get_by_name(ctx.author.id, argument)

        if task is not None:
            return task["todo_id"]

        if not self.required:
            return None

        raise commands.CommandInvokeError(
            ValueError("Could not find task with name or ID " + argument),
        )


class EmojiConverter(commands.Converter[discord.Emoji]):
    async def convert(self, ctx: VanirContext, argument: str) -> discord.Emoji:
        if not (match := EMOJI_REGEX.fullmatch(argument)):
            msg = "Invalid emoji format"
            raise commands.BadArgument(msg)

        if not (emoji := ctx.bot.get_emoji(int(match.group("id")))):
            msg = "Emoji not found"
            raise commands.BadArgument(msg)

        return emoji
