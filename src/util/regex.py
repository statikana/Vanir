import re

# from src.constants import MATH_GLOBALS_MAP

EMOJI_REGEX = re.compile(
    r"<(?P<animated>a?):(?P<name>[A-z0-9_]{2,32}):(?P<id>[0-9]{18,22})>"
)
SNOWFLAKE_REGEX = re.compile(r"[0-9]{15,20}")
SLUG_REGEX = re.compile(r"[^a-z0-9\-]")

URL_REGEX = re.compile(
    r"https?://([a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(%[0-9a-fA-F][0-9a-fA-F]))+"
)


SPACE_FORMAT_REGEX = re.compile(r"(?P<last>[0-9]) (?P<start>[A-z])")
SPACE_SUB_REGEX = r"\g<last>\g<start>"

DISCORD_TIMESTAMP_REGEX = re.compile(r"<t:(?P<ts>[0-9]{0,12})(?::[RFfDdTt])?>")
TIMESTAMP_REGEX_REGEX = re.compile(r"^[0-9]{0,12}(\.[0-9]{1,10})?$")

CONNECTOR_REGEX = r"(and|,|\t|  )"

MATH_EXPRESSION_REGEX = re.compile(
    r"(?P<funcname>[a-z]{2,10})\((?P<params>(?:([0-9]+(?:, ?)?))+)\)"
)
OPERATOR_EXPRESSION_REGEX = re.compile(
    r"(?P<lhs>[0-9]+)(?P<operator>[+\-*/(**)])(?P<rhs>[0-9]+)"
)

CODEBLOCK_REGEX = re.compile(
    r"(`{3}(?P<lang>[a-zA-z]*)\n?(?P<codelong>[^`]*)\n?`{3}|`(?P<codeshort>[^`]*)`)"
)
