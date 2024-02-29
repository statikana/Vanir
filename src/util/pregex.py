import re

EMOJI_RE = re.compile(r"<a?:[A-z0-9_]{2,32}:[0-9]{18,22}>")
SNOWFLAKE_REGEX = re.compile(r"[0-9]{15,20}")