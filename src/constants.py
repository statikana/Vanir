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
    0: "reset",  # we'll pretend this isn't dumb
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
