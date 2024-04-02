import math
from typing import NamedTuple

LANGUAGE_CODE_MAP = {
    "AR": "Arabic",
    "BG": "Bulgarian",
    "CS": "Czech",
    "DA": "Danish",
    "DE": "German",
    "EL": "Greek",
    "EN": "English",
    "ES": "Spanish",
    "ET": "Estonian",
    "FI": "Finnish",
    "FR": "French",
    "HU": "Hungarian",
    "ID": "Indonesian",
    "IT": "Italian",
    "JA": "Japanese",
    "KO": "Korean",
    "LT": "Lithuanian",
    "LV": "Latvian",
    "NB": "Norwegian",
    "NL": "Dutch",
    "PL": "Polish",
    "PT": "Portuguese",
    "RO": "Romanian",
    "RU": "Russian",
    "SK": "Slovak",
    "SL": "Slovenian",
    "SV": "Swedish",
    "TR": "Turkish",
    "UK": "Ukrainian",
    "ZH": "Chinese",
}

LANGUAGE_NAME_MAP = {v: k for k, v in LANGUAGE_CODE_MAP.items()}

LANGUAGE_CODES = set(LANGUAGE_CODE_MAP.keys())
LANGUAGE_NAMES = set(LANGUAGE_NAME_MAP.keys())

VALID_VIDEO_FORMATS = ("webm", "mp4")

VALID_IMAGE_FORMATS = ("jpg", "jpeg", "png")

STRONG_CHANNEL_PERMISSIONS = (
    "administrator",
    "manage_messages",
    "manage_channels",
    "manage_permissions",
    "manage_roles",
    "manage_guild",
    "manage_threads",
    "manage_webhooks",
    "mention_everyone",
)

GLOBAL_CHANNEL_PERMISSIONS = (
    "create_instant_invite",
    "manage_webhooks",
    "view_channel",
)

TEXT_CHANNEL_PERMISSIONS = (
    "add_reactions",
    "attach_files",
    "create_private_threads",
    "create_public_threads",
    "embed_links",
    "manage_messages",
    "manage_threads",
    "mention_everyone",
    "read_message_history",
    "send_messages",
    "send_messages_in_threads",
    "send_tts_messages",
    "send_voice_messages",
    "send_voice_messages",
    "use_application_commands",
    "use_external_emojis",
    "use_external_stickers",
)

VOICE_CHANNEL_PERMISSIONS = (
    "connect",
    "deafen_members",
    "move_members",
    "mute_members",
    "priority_speaker",
    "speak",
    "use_soundboard",
    "use_voice_activation",
)

ALL_PERMISSIONS = (
    STRONG_CHANNEL_PERMISSIONS
    + GLOBAL_CHANNEL_PERMISSIONS
    + TEXT_CHANNEL_PERMISSIONS
    + VOICE_CHANNEL_PERMISSIONS
)

GITHUB_ROOT = "https://github.com/statikana/Vanir"

ANSI_CODES = {
    00: "reset",  # we'll pretend this isn't dumb
    30: "grey",
    31: "red",
    32: "green",
    33: "yellow",
    34: "blue",
    35: "pink",
    36: "cyan",
    37: "white",
}

ANSI = {name: f"\N{ESCAPE}[0;{code}m" for code, name in ANSI_CODES.items()}
ANSI_EMOJIS = {
    "grey": "\U0001fa76",
    "red": "\U00002764",
    "green": "\U0001f49a",
    "yellow": "\U0001f49b",
    "blue": "\U0001f499",
    "pink": "\U0001fa77",
    "cyan": "\U0001fa75",
    "white": "\U0001f90d",
}

POS_COLORS = {
    "LS": "white",  # list item marker
    "TO": "white",  # "to" as in "to be"
    "''": "grey",  # closing quotation mark
    "--": "grey",  # dash
    ".": "grey",  # sentence terminator
    ",": "grey",  # comma
    ":": "grey",  # colon or ellipsis
    "(": "grey",  # opening parenthesis
    ")": "grey",  # closing parenthesis
    "DT": "grey",  # determiner
    "IN": "blue",  # preposition or conjunction
    "UH": "yellow",  # interjection
    "VB": "green",  # verb, base form
    "VBG": "green",  # verb, gerund or present participle
    "VBD": "green",  # verb, past tense
    "VBZ": "green",  # verb, 3rd person singular present
    "VBP": "green",  # verb, non-3rd person singular present
    "VBN": "green",  # verb, past participle
    "JJ": "cyan",  # adjective
    "DT$": "pink",  # possessive determiner
    "PRP": "pink",  # pronoun, personal
    "PRP$": "pink",  # pronoun, possessive
    "WP": "white",  # wh-pronoun
    "WP$": "white",  # possessive wh-pronoun
    "NNP": "white",  # proper noun, singular
    "NN": "white",  # noun, singular or mass
    "NNS": "grey",  # noun, plural
    "NNPS": "grey",  # proper noun, plural
    "CC": "blue",  # coordinating conjunction
    "RB": "red",  # adverb
    "RBR": "red",  # adverb, comparative
    "RBS": "red",  # adverb, superlative
    "MD": "yellow",  # verb, modal auxiliary
    "CD": "white",  # cardinal number
    "SYM": "white",  # symbol
    "POS": "white",  # possessive ending
    "EX": "white",  # existential there
    "FW": "white",  # foreign word
    "PDT": "pink",  # predeterminer
    "RP": "red",  # particle
    "WDT": "pink",  # wh-determiner
}

MONOSPACE_FONT_HEIGHT_RATIO = 1.6


class VanirEmoji(NamedTuple):
    name: str
    id: int
    animated: bool
    description: str = ""

    def __str__(self) -> str:
        return f"<{"a" if self.animated else ""}:{self.name}:{self.id}>"

    __repr__ = __str__


EMOJIS = {
    "b_arrow": VanirEmoji(name="b_arrow", id=1220034776426352670, animated=False),
    "bb_arrow": VanirEmoji(name="bb_arrow", id=1220035023827374080, animated=False),
    "f_arrow": VanirEmoji(name="f_arrow", id=1220034630992789575, animated=False),
    "ff_arrow": VanirEmoji(name="ff_arrow", id=1220034497454801006, animated=False),
    "close": VanirEmoji(name="close", id=1220186816225874091, animated=False),
    "execute": VanirEmoji(name="execute", id=1220179060928282805, animated=False),
    "info": VanirEmoji(name="info", id=1220177488886501529, animated=False),
    "patreon": VanirEmoji(name="patreon", id=1220769788159066132, animated=False),
    "pixiv": VanirEmoji(name="pixiv", id=1220769964030431243, animated=False),
    "x": VanirEmoji(name="x", id=1220770263566778529, animated=False),
    "deviant_art": VanirEmoji(
        name="deviant_art",
        id=1220770290670244042,
        animated=False,
    ),
    "waifuim": VanirEmoji(name="waifuim", id=1220801796977725531, animated=False),
    "timeout": VanirEmoji(
        name="timeout",
        id=1222339703613816842,
        animated=False,
        description="Timed Out",
    ),
    "kick": VanirEmoji(
        name="kick",
        id=1222340933119512736,
        animated=False,
        description="Kicked",
    ),
    "ban": VanirEmoji(
        name="ban",
        id=1222341200397205655,
        animated=False,
        description="Banned",
    ),
    "piston": VanirEmoji(name="piston", id=1223830801938911253, animated=False),
    "bdg_active_developer": VanirEmoji(
        name="bdg_active_developer",
        id=1223845037163544718,
        animated=False,
        description="Active Developer",
    ),
    "bdg_bug_hunter": VanirEmoji(
        name="bdg_bug_hunter",
        id=1223845051130708071,
        animated=False,
        description="Bug Hunter",
    ),
    "bdg_bug_hunter_level_2": VanirEmoji(
        name="bdg_bug_hunter_level_2",
        id=1223845064997081120,
        animated=False,
        description="Golden Bug Hunter",
    ),
    "bdg_discord_staff": VanirEmoji(
        name="bdg_discord_staff",
        id=1223845079178022974,
        animated=False,
        description="Discord Staff",
    ),
    "bdg_early_supporter": VanirEmoji(
        name="bdg_early_supporter",
        id=1223845093459361842,
        animated=False,
        description="Early Supporter",
    ),
    "bdg_early_verified_bot_developer": VanirEmoji(
        name="bdg_early_verified_bot_developer",
        id=1223845107720126535,
        animated=False,
        description="Early Verified Bot Developer",
    ),
    "bdg_hypesquad_events": VanirEmoji(
        name="bdg_hypesquad_events",
        id=1223845121888485486,
        animated=False,
        description="HypeSquad Events",
    ),
    "bdg_hypesquad_balance": VanirEmoji(
        name="bdg_hypesquad_balance",
        id=1223845136102850702,
        animated=False,
        description="HypeSquad Balance",
    ),
    "bdg_hypesquad_bravery": VanirEmoji(
        name="bdg_hypesquad_bravery",
        id=1223845150267015249,
        animated=False,
        description="HypeSquad Bravery",
    ),
    "bdg_hypesquad_brilliance": VanirEmoji(
        name="bdg_hypesquad_brilliance",
        id=1223846361678610523,
        animated=False,
        description="HypeSquad Brilliance",
    ),
    "bdg_moderator_programs_alumni": VanirEmoji(
        name="bdg_moderator_programs_alumni",
        id=1223846375503036446,
        animated=False,
        description="Mod. Programs Alumni",
    ),
    "bdg_nitro": VanirEmoji(
        name="bdg_nitro",
        id=1223846389700628532,
        animated=False,
        description="Nitro",
    ),
    "bdg_partnered_server_owner": VanirEmoji(
        name="bdg_partnered_server_owner",
        id=1223846404053667881,
        animated=False,
        description="Partnered Server Owner",
    ),
    "bdg_server_partner": VanirEmoji(
        name="bdg_server_partner",
        id=1223846418238800082,
        animated=False,
        description="Server Partner",
    ),
    "bdg_server_verified": VanirEmoji(
        name="bdg_server_verified",
        id=1223846432176603196,
        animated=False,
        description="Server Verified",
    ),
    "bdg_bot": VanirEmoji(
        name="bdg_bot",
        id=1223853099471474689,
        animated=False,
        description="Bot",
    ),
    "bdg_verified_bot": VanirEmoji(
        name="bdg_verified_bot",
        id=1223853476036218950,
        animated=False,
        description="Verified Bot",
    ),
    "tag": VanirEmoji(name="tag", id=1223855353540775937, animated=False),
    "join": VanirEmoji(name="join", id=1223858211866677349, animated=False),
    "new": VanirEmoji(name="new", id=1223858039799414824, animated=False),
    "github": VanirEmoji(name="github", id=1224196311545413704, animated=False),
    "bw_info": VanirEmoji(name="bw_info", id=1224536530563891292, animated=False),
    "role": VanirEmoji(name="role", id=1224540138814570647, animated=False),
    
    "mobile": VanirEmoji(name="mobile", id=1224542517937049670, animated=False),
    "desktop": VanirEmoji(name="desktop", id=1224542647163551755, animated=False),
    "web": VanirEmoji(name="web", id=1224544021591097384, animated=False),
    
    "offline": VanirEmoji(name="offline", id=1224552198126567456, animated=False),
    "invisible": VanirEmoji(name="offline", id=1224552198126567456, animated=False), # offline
    "idle": VanirEmoji(name="idle", id=1224552076646944828, animated=False),
    "dnd": VanirEmoji(name="dnd", id=1224552124516536342, animated=False),
    "online": VanirEmoji(name="online", id=1224552158045671434, animated=False),
    
    "status": VanirEmoji(name="status", id=1224551297424949308, animated=False),
    "boost": VanirEmoji(name="boost", id=1224561790797611009, animated=False),
    "person": VanirEmoji(name="person", id=1224563879384711188, animated=False),
    "shield": VanirEmoji(name="shield", id=1224564433687154769, animated=False),
}

TIMESTAMP_STYLES = {
    "": "Default",
    "t": "Short Time",
    "T": "Long Time",
    "d": "Short Date",
    "D": "Long Date",
    "f": "Short Date/Time",
    "F": "Long Date/Time",
    "R": "Relative Time",
}

TIME_UNITS = {
    "years": 60 * 60 * 24 * 365,
    "months": 60 * 60 * 24 * 30,
    "weeks": 60 * 60 * 24 * 7,
    "days": 60 * 60 * 24,
    "hours": 60 * 60,
    "minutes": 60,
    "seconds": 1,
}

# Functions that are safe to evaluate user content from
# mostly math stuff
MATH_GLOBALS_MAP = {
    # math funcs
    "abs": abs,
    "acos": math.acos,
    "acosh": math.acosh,
    "asin": math.asin,
    "asinh": math.asinh,
    "atan": math.atan,
    "atan2": math.atan2,
    "atanh": math.atanh,
    "ceil": math.ceil,
    "comb": math.comb,
    "copysign": math.copysign,
    "cos": math.cos,
    "cosh": math.cosh,
    "degrees": math.degrees,
    "dist": math.dist,
    "erf": math.erf,
    "erfc": math.erfc,
    "exp": math.exp,
    "expm1": math.expm1,
    "fabs": math.fabs,
    "factorial": math.factorial,
    "floor": math.floor,
    "fmod": math.fmod,
    "frexp": math.frexp,
    "fsum": math.fsum,
    "gamma": math.gamma,
    "gcd": math.gcd,
    "hypot": math.hypot,
    "isclose": math.isclose,
    "isfinite": math.isfinite,
    "isinf": math.isinf,
    "isnan": math.isnan,
    "isqrt": math.isqrt,
    "ldexp": math.ldexp,
    "lgamma": math.lgamma,
    "log": math.log,
    "log10": math.log10,
    "log1p": math.log1p,
    "log2": math.log2,
    "perm": math.perm,
    "pow": math.pow,
    "prod": math.prod,
    "radians": math.radians,
    "remainder": math.remainder,
    "sin": math.sin,
    "sinh": math.sinh,
    "sqrt": math.sqrt,
    "tan": math.tan,
    "tanh": math.tanh,
    "trunc": math.trunc,
    # python funcs
    "any": any,
    "all": all,
    "max": max,
    "min": min,
    "sum": sum,
    "round": round,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "tuple": tuple,
    "set": set,
    "dict": dict,
    "len": len,
    "zip": zip,
    "enumerate": enumerate,
    "range": range,
    "reversed": reversed,
    "sorted": sorted,
    "filter": filter,
    "map": map,
    # operator replacements
    "add": lambda a, b: a + b,
    "sub": lambda a, b: a - b,
    "mul": lambda a, b: a * b,
    "div": lambda a, b: a / b,
    "mod": lambda a, b: a % b,
    "floordiv": lambda a, b: a // b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "ge": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
    "not": lambda a: not a,
    "xor": lambda a, b: a ^ b,
    "lshift": lambda a, b: a << b,
    "rshift": lambda a, b: a >> b,
    "invert": lambda a: ~a,
    "print": print,
}
