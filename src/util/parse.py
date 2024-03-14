import typing
from enum import Enum
from urllib.parse import urlparse

from fuzzywuzzy import fuzz

from src.constants import COLOR_INDEX
from src.util.pregex import SLUG_REGEX


FuzzyT = typing.TypeVar("FuzzyT")


def find_filename(url: str):
    path = urlparse(url).path.rstrip("/")
    return path[path.rfind("/") + 1 :]


def find_ext(url: str):
    filename = find_filename(url)
    return filename[filename.rfind(".") + 1 :]


def closest_color_name(start_hex: str) -> tuple[str, int]:
    start = int(start_hex, 16)
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
) -> list[FuzzyT]:
    pairs: list[tuple[FuzzyT, int]] = [
        (s, fuzz.partial_token_set_ratio(source, key(s))) for s in values
    ]

    std = sorted(pairs, key=lambda t: t[1], reverse=True)

    flt = filter(lambda t: t[1] >= threshold, std)

    out = list(output(v[0]) for v in flt)

    return out


class Convention(Enum):
    DECIMAL = 0
    BINARY = 1
