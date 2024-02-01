from typing import Any
from urllib import parse
import re


def ensure_slug(slug: str) -> str:
    return re.sub(r"[^a-z0-9\-]", "", slug).lower().strip(" .-")


def format_dict(data: dict[Any, Any]):
    return "\n".join(f"**{str(k)}:** *{str(v)}*" for k, v in data.items())

