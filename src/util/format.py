from __future__ import annotations

import math
from typing import Any, Generator, Iterable

from src.constants import ANSI
from src.util.parse import Convention
from src.util.regex import CODEBLOCK_REGEX


def fmt_dict(
    data: dict[Any, Any],
    linesplit: bool = False,
    colons: bool = True,
) -> str:
    lines: list[str] = []
    for k, v in data.items():
        v_str = f"{v}"
        lines.append(
            f"**{k}**{":" if colons else ""}{"\n. . ." if linesplit else ""} {v_str}"
        )

    return "\n".join(lines)


def fmt_size(n_bytes: int, cvtn: Convention = Convention.BINARY) -> str:
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


def fmt_bool(b: bool) -> str:  # ignore[boolean-type-hint-positional-argument]
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
