from enum import Enum
import re
from urllib.parse import urlparse

from src.constants import COLOR_INDEX
from src.util.pregex import SLUG_REGEX


def find_filename(url: str):
    path = urlparse(url).path.rstrip("/")
    return path[path.rfind("/") + 1 :]


def find_ext(url: str):
    filename = find_filename(url)
    return filename[filename.rfind(".") + 1 :]


def closest_name(start_hex: str) -> tuple[str, int]:
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


class Convention(Enum):
    DECIMAL = 0
    BINARY = 1
