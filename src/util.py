import inspect
from datetime import datetime
from typing import Any
import re
from discord.ext import commands


def ensure_slug(slug: str) -> str:
    return re.sub(r"[^a-z0-9\-]", "", slug).lower().strip(" .-")


def format_dict(
    data: dict[Any, Any], miss_keys: list[Any] = None, linesplit: bool = False
) -> str:
    if miss_keys is None:
        miss_keys = []
    lines: list[str] = []
    for k, v in data.items():
        if k not in miss_keys:
            v_str = f"*{v}*"
        else:
            v_str = f"{v}"
        if linesplit:
            lines.append(f"**{k}**:\n. . . {v_str}")
        else:
            lines.append(f"**{k}**: {v_str}")

    return "\n".join(lines)


def readable_iso8601(date: datetime) -> str:
    return date.strftime("%H:%M, %d %b, %Y")


def discover_cog(cog: commands.Cog) -> set[commands.Command]:
    cs = cog.get_commands()
    end = set()
    for command in cs:
        if isinstance(command, commands.Group):
            end.update(discover_group(command))
        else:
            end.add(command)

    return end


def discover_group(group: commands.Group) -> set[commands.Command]:
    end = group.commands
    for s in end:
        if isinstance(s, commands.Group):
            end.update(s.commands)
        else:
            end.add(s)

    return end


def get_display_cogs(bot: commands.Bot) -> list[commands.Cog]:
    return [c for c in bot.cogs.values() if not getattr(c, "hidden", False)]


def get_param_annotation(param: inspect.Parameter) -> str:
    ptype = param.annotation

    if str(ptype).endswith(">"):
        return ptype.__name__

    if hasattr(ptype, "min"):  # this is a .Range
        rtype_name = getattr(ptype, "annotation").__name__  # eg <class 'int'> -> int
        range_min = getattr(ptype, "min")
        range_max = getattr(ptype, "max")

        if rtype_name == "int":
            rtype_name = "integer"
        if rtype_name == "float":
            rtype_name = "decimal"

        if range_min is None:
            return f"{rtype_name} <= {range_max}"
        elif range_max is None:
            return f"{rtype_name} >= {range_min}"
        else:
            return f"{range_min} <= {rtype_name} <= {range_max}"
    return str(ptype)
