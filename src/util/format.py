from __future__ import annotations

import math
from typing import Any, Generator, Iterable, overload

from src.constants import ANSI, EMOJIS
from src.util.parse import Convention
from src.util.regex import CODEBLOCK_REGEX


def format_dict(
    data: dict[Any, Any],
    linesplit: bool = False,
    colons: bool = True,
) -> str:
    lines: list[str] = []
    for k, v in data.items():
        v_str = f"{v}"
        lines.append(
            f"**{k}**{":" if colons else ""}{"\n. . ." if linesplit else ""} {v_str}",
        )

    return "\n".join(lines)


@overload
def format_children(
    *,
    emoji: str,
    title: str,
    children: list[tuple[str, str]],
    as_field: bool = False,
) -> str: ...


@overload
def format_children(
    *,
    emoji: str,
    title: str,
    children: list[tuple[str, str]],
    as_field: bool = True,
) -> list[str]: ...


def format_children(
    *,
    emoji: str,
    title: str,
    children: list[tuple[str, str]],
    as_field: bool = False,
    rjust: bool = False,
) -> list[str] | str:
    con_line = EMOJIS["down_split_right_curve"]
    fin_line = EMOJIS["down_right_curve"]

    lines: list[str] = [f"{emoji} **{title}**"]

    maxn = max(len(k) for k, _ in children)

    for i, (k, v) in enumerate(children):
        key = k.rjust(maxn, " ") if k and rjust else k

        key = f"**{key}:** " if key else ""

        if i == len(children) - 1:
            lines.append(f"{fin_line}{key}{v}")
        else:
            lines.append(f"{con_line}{key}{v}")
    if not as_field:
        return "\n".join(lines)
    else:
        return [lines[0], "\n".join(lines[1:])]


def format_size(n_bytes: int, cvtn: Convention = Convention.BINARY) -> str:
    if cvtn == Convention.BINARY:
        size_factor = math.log(n_bytes, 2) // 10
    else:
        size_factor = math.log(n_bytes, 1000) // 1

    ext: str
    match round(size_factor):
        case 0:
            ext = "B"
        case 1:
            ext = "KiB"
        case 2:
            ext = "MiB"
        case 3:
            ext = "GiB"
        case 4:
            ext = "TiB"
        case 5:
            ext = "PiB"
        case 6:
            ext = "EiB"
        case 7:
            ext = "ZiB"
        case 8:
            ext = "YiB"
        case _:
            ext = "..."

    if cvtn == Convention.BINARY:
        n_bytes_factored = float(n_bytes) / (2 ** (10 * size_factor))
    else:
        n_bytes_factored = float(n_bytes) / (1000**size_factor)
        ext = ext.replace("i", "")
        ext = ext[:1].lower() + ext[1:]

    nb_fmt = round(n_bytes_factored, 3)
    if nb_fmt // 1 == nb_fmt:
        nb_fmt = int(nb_fmt)

    return f"{nb_fmt} {ext}"


def ctext(text: str, color: str) -> str:
    return f"{ANSI[color]}{text}{ANSI['reset']}"


def format_bool(b: bool) -> str:  # ignore[boolean-type-hint-positional-argument]
    return ctext("Yes", color="green") if b else ctext("No", color="red")


def natural_join(it: Iterable[str]) -> str:
    if isinstance(it, Generator):
        it = list(it)
    n = len(it)
    match n:
        case 0:
            return ""
        case 1:
            return it[0]
        case 2:
            return f"{it[0]} and {it[1]}"
        case _:
            return f"{', '.join(it[:-1])}, and {it[-1]}"


def trim_codeblock(text: str) -> str:
    match = CODEBLOCK_REGEX.fullmatch(text)
    if match is None:
        return text
    try:
        code = match.group("codelong")
    except IndexError:
        code = match.group("codeshort")
    return code.strip()


def wrap_text(text: str, max_chars: int = 30, wrap_char: str = "<br>") -> str:
    """
    Wraps text at a character limit and returns a string
    with line breaks (<br>) for each wrapped line.
    """
    words = text.split()  # Split text into words
    wrapped_lines = []
    current_line = ""
    for word in words:
        if len(current_line + word) <= max_chars:  # Check if word fits in current line
            current_line += word + " "
        else:
            wrapped_lines.append(
                current_line[:-1],
            )  # Add previous line without trailing space
            current_line = word + " "
    wrapped_lines.append(current_line[:-1])  # Add the last line
    return wrap_char.join(wrapped_lines)  # Join lines with line breaks
