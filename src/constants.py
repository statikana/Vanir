from typing import NamedTuple

from assets.color_db import COLORS as COLOR_INDEX  # type: ignore

LANGUAGE_NAMES = {
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

LANGUAGE_CODES = {v: k for k, v in LANGUAGE_NAMES.items()}

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

MONOSPACE_FONT_HEIGHT_RATIO = 1.6


class VanirEmoji(NamedTuple):
    name: str
    id: int
    animated: bool

    def __str__(self):
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
        name="deviant_art", id=1220770290670244042, animated=False
    ),
    "waifuim": VanirEmoji(name="waifuim", id=1220801796977725531, animated=False),
}
