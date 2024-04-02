from __future__ import annotations

import typing
import unicodedata
from enum import Enum
from multiprocessing import Pool
from urllib.parse import urlparse

from fuzzywuzzy import fuzz

from assets.color_db import COLOR_INDEX
from src.util.regex import SLUG_REGEX

FuzzyT = typing.TypeVar("FuzzyT")
T = typing.TypeVar("T")
K = typing.TypeVar("K")


class Convention(Enum):
    DECIMAL = 0
    BINARY = 1


def find_filename(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path[path.rfind("/") + 1 :]


def find_ext(url: str) -> str:
    filename = find_filename(url)
    return filename[filename.rfind(".") + 1 :]


def closest_color_name(start_hex: str) -> tuple[str, int]:
    start = int(start_hex.strip("#"), 16)
    best: tuple[str, int] | None = None
    for col, (check_hex, _) in COLOR_INDEX.items():
        if best is None:
            best = col, abs(int(check_hex[1:], 16) - start)

        dif = abs(int(check_hex[1:], 16) - start)

        if dif < best[1]:
            best = col, dif

    return best


def ensure_slug(slug: str) -> str:
    return SLUG_REGEX.sub("", slug).lower().strip(" .-")


def fuzzysearch(
    source: str,
    values: list[FuzzyT],
    /,
    *,
    key: typing.Callable[[FuzzyT], str] = lambda f: str(f),
    output: typing.Callable[[FuzzyT], typing.Any] = lambda v: v,
    threshold: int = 0,
    judge: typing.Callable[[str, str], int] = fuzz.partial_token_set_ratio,
) -> list[FuzzyT]:
    pairs: list[tuple[FuzzyT, int]] = [(s, judge(source, key(s))) for s in values]

    std = sorted(pairs, key=lambda t: t[1], reverse=True)

    flt = filter(lambda t: t[1] >= threshold, std)

    return [output(v[0]) for v in flt]


def fuzzysearch_thread(
    source: str,
    values: list[FuzzyT],
    /,
    *,
    key: typing.Callable[[FuzzyT], str] | None = None,
    output: typing.Callable[[FuzzyT], typing.Any] | None = None,
    threshold: int = 0,
    judge: typing.Callable[[str, str], int] = fuzz.partial_token_set_ratio,
) -> typing.Generator[FuzzyT, None, None]:
    if key is not None:
        values = map(key, values)
    with Pool() as pool:
        result = pool.starmap(
            lambda v: judge(source, v),
            values,
        )

    for i, v in enumerate(values):
        if result[i] >= threshold:
            yield output(v) if output is not None else v


def unique(
    iterable: typing.Iterable[T],
    key: typing.Callable[[T], typing.Any] = lambda x: x,
) -> list[T]:
    seen = set()
    out = []
    for item in iterable:
        k = key(item)
        if k not in seen:
            seen.add(k)
            out.append(item)
    return out


def soundex(string: str) -> str:
    # https://stackoverflow.com/a/67197882
    if not string:
        return ""

    string = unicodedata.normalize("NFKD", string)
    string = string.upper()

    replacements = (
        ("BFPV", "1"),
        ("CGJKQSXZ", "2"),
        ("DT", "3"),
        ("L", "4"),
        ("MN", "5"),
        ("R", "6"),
    )
    result = [string[0]]
    count = 1

    for lset, sub in replacements:
        if string[0] in lset:
            last = sub
            break
    else:
        last = None

    for letter in string[1:]:
        for lset, sub in replacements:
            if letter in lset:
                if sub != last:
                    result.append(sub)
                    count += 1
                last = sub
                break
        else:
            if letter not in ("H", "W"):
                # leave last alone if middle letter is H or W
                last = None
        if count == 4:
            break

    result += "0" * (4 - count)
    return "".join(result)
