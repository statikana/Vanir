import time
from asyncio import iscoroutinefunction
from dataclasses import dataclass

import discord
from discord.app_commands import Choice


LANGUAGE_INDEX = {
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


@dataclass
class MessageState:
    content: str
    embeds: list[discord.Embed]
    items: list[discord.ui.Item]

    def __str__(self):
        return f"{self.content or '_'} -  {','.join(e.title for e in self.embeds)} - {len(self.items)} children"

    def __repr__(self):
        return self.__str__()


async def timeit(func, *args):
    if iscoroutinefunction(func):
        start = time.time()
        await func(*args)
    else:
        start = time.time()
        func(*args)

    return time.time() - start


async def langcode_autocomplete(itx: discord.Interaction, current: str):
    options = [Choice(name=f"{v} [{k}]", value=k) for k, v in LANGUAGE_INDEX.items()][
        :25
    ]
    options = sorted(
        filter(lambda c: current.lower() in c.name.lower(), options),
        key=lambda c: c.name,
    )
    return options


