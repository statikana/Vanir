import re

EMOJI_REGEX = re.compile(
    r"<(?P<animated>a?):(?P<name>[A-z0-9_]{2,32}):(?P<id>[0-9]{18,22})>"
)
SNOWFLAKE_REGEX = re.compile(r"[0-9]{15,20}")
SLUG_REGEX = re.compile(r"[^a-z0-9\-]")

URL_REGEX = re.compile(
    r"https?://([a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(%[0-9a-fA-F][0-9a-fA-F]))+"
)
