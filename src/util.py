from datetime import datetime
from typing import Any
import re
from dateutil import parser


def ensure_slug(slug: str) -> str:
    return re.sub(r"[^a-z0-9\-]", "", slug).lower().strip(" .-")


def format_dict(data: dict[Any, Any], miss_keys: list[Any]) -> str:
    lines: list[str] = []
    for k, v in data.items():
        if k not in miss_keys:
            lines.append(f"**{k}**: *{v}*")
        else:
            lines.append(f"**{k}**: {v}")

    return "\n".join(lines)


def readable_iso8601(date: datetime) -> str:
    return date.strftime("%H:%M, %d %b, %Y")
