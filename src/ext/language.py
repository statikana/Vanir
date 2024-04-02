from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import nltk
from discord import app_commands
from discord.ext import commands

from src.constants import (
    ANSI,
    LANGUAGE_CODE_MAP,
    LANGUAGE_CODES,
    LANGUAGE_NAME_MAP,
    LANGUAGE_NAMES,
    POS_COLORS,
)
from src.types.command import VanirCog, VanirView, vanir_command
from src.util.command import langcode_autocomplete

if TYPE_CHECKING:
    from src.types.core import Vanir, VanirContext


class Language(VanirCog):
    """Definitions / Translations."""

    emoji = "\N{OPEN BOOK}"

    @vanir_command(aliases=["def", "d"])
    async def define(
        self,
        ctx: VanirContext,
        *,
        term: str = commands.param(description="The term to define"),
    ) -> None:
        """Defines a word."""
        url = "https://api.dictionaryapi.dev/api/v2/entries/en/"
        response = await self.bot.session.get(url + term)

        if response.status != 200:
            embed = ctx.embed(
                f"Could not find a definition for {term}",
                color=discord.Color.red(),
            )
            return await ctx.reply(embed=embed)

        json = (await response.json())[0]
        title = f"{term}"

        if json.get("phonetic"):
            title += f" [{json['phonetic']}]"

        embed = ctx.embed(title, url=json["sourceUrls"][0])
        view = VanirView(self.bot)

        for regional_phonetic in json["phonetics"]:
            if audio_file := regional_phonetic["audio"]:
                view.add_item(
                    discord.ui.Button(
                        style=discord.ButtonStyle.url,
                        label=f"{audio_file[audio_file.rfind('-')+1:audio_file.rfind('.')].upper()} Pronunciation",
                        emoji="\N{SPEAKER WITH THREE SOUND WAVES}",
                        url=audio_file,
                    ),
                )

        def format_def(definition: dict):
            format_definition = f"**{i + 1}.** {discord.utils.escape_markdown(definition['definition'])}"
            if "example" in definition:
                format_definition += (
                    f"\n\t> *{discord.utils.escape_markdown(definition['example'])}*"
                )
            return format_definition

        for meaning in json["meanings"]:
            definitions = []
            len_sum = 0

            for i, d in enumerate(meaning["definitions"]):
                formatted = format_def(d)
                n_chars = len(formatted)
                if len(formatted) + len_sum <= 980:
                    definitions.append(formatted)
                    len_sum += n_chars
                else:
                    n_broken = len(meaning["definitions"]) - i
                    definitions.append(f"\n***> ... {n_broken} definitions trimmed***")
                    break

            value = "\n".join(definitions)[:1024]

            embed.add_field(
                name=f"as ***{meaning['partOfSpeech']}***",
                value=value,
                inline=False,
            )

        await ctx.reply(embed=embed, view=view)
        return None

    @vanir_command(aliases=["tl"])
    @app_commands.autocomplete(
        source_lang=langcode_autocomplete,
        target_lang=langcode_autocomplete,
    )
    @commands.cooldown(5, 60, commands.BucketType.user)
    async def translate(
        self,
        ctx: VanirContext,
        target_lang: str | None = commands.param(
            description="The language to translate to",
            default=None,
        ),
        *,
        text: str = commands.param(
            description="The text to translate",
            default=None,
            displayed_default="<reference message's text>",
        ),
        source_lang: str = commands.param(
            description="The language to translate from",
            default="AUTO",
        ),
    ) -> None:
        """Translates the text from one language to another."""
        if isinstance(source_lang, commands.Parameter):
            source_lang = source_lang.default
        if isinstance(target_lang, commands.Parameter):
            target_lang = target_lang.default

        if target_lang is None:
            target_lang = "EN"
        elif target_lang.title() in LANGUAGE_NAMES:
            target_lang = LANGUAGE_NAME_MAP[target_lang.title()]
        elif target_lang.upper() not in LANGUAGE_CODES:
            target_lang = target_lang.upper()
        else:
            text = f"{target_lang} {text if text else ''}"
            target_lang = "EN"

        source_lang = source_lang.upper()
        target_lang = target_lang.upper()

        if text is None:
            if ctx.message.reference is not None:
                full_ref = await ctx.channel.fetch_message(
                    ctx.message.reference.message_id,
                )
                text = full_ref.content
            else:
                async for m in ctx.channel.history(limit=20):
                    if (
                        m.id != ctx.message.id
                        and m.content
                        and not m.content.startswith(ctx.prefix)
                    ):
                        text = m.content
                        break
                else:
                    msg = "No text could be found."
                    raise ValueError(msg)

        text = text[:100]

        json = {
            "text": [text],
            "target_lang": target_lang,
        }
        if source_lang != "AUTO":
            json["source_lang"] = source_lang
        response = await self.bot.session.deepl("/translate", json=json)
        response.raise_for_status()
        tsl = (await response.json())["translations"][0]

        source = LANGUAGE_CODE_MAP[tsl["detected_source_language"]]
        target = LANGUAGE_CODE_MAP[target_lang]

        embed = ctx.embed(description=tsl["text"])
        embed.set_footer(
            text=f"{source} -> {target}",
        )
        view = AfterTranslateView(
            ctx,
            tsl["detected_source_language"],
            target_lang,
            tsl["text"],
        )
        await ctx.reply(embed=embed, view=view)

    @vanir_command()
    async def pos(
        self,
        ctx: VanirContext,
        *,
        text: str = commands.param(
            description="The text to tag parts of speech",
        ),
    ) -> None:
        """Tags parts of speech in the text."""
        text = text[:130]
        tokens = nltk.word_tokenize(text)
        tagged = nltk.pos_tag(tokens)

        tag_map = nltk.data.load("help/tagsets/upenn_tagset.pickle")
        relavant_tags = {
            k: v[0] for k, v in tag_map.items() if k in (t[1] for t in tagged)
        }
        desc = format_pos_tags(tagged, relavant_tags)
        
        await ctx.reply(f"```ansi\n{desc}```")

    @vanir_command()
    async def autocorrect(
        self,
        ctx: VanirContext,
        *,
        word_or_phrase: str = commands.param(
            description="The word or phrase to autocorrect",
        ),
    ) -> None:
        if len(word_or_phrase.split()) == 1:
            config = self.bot.cache.fuzzy_ac.config
            contianer = self.bot.cache.fuzzy_ac.possible(
                word_or_phrase,
                distance=2,
                n=10,
            )
            values = sorted(
                contianer.stack,
                key=lambda pack: (
                    config.levenshtein_offset - pack[1][0],
                    1 - pack[1][1],
                ),
            )
            try:
                maxlen = max(len(word) for word, _ in values)
            except ValueError as err:
                msg = "No words found"
                raise ValueError(msg) from err
            words = [
                f"`{word:<{maxlen}}` [D: `{config.levenshtein_offset-distance}`, P: `{proportion*100:.2f}`]"
                for word, (distance, proportion) in values
            ]
            embed = ctx.embed(
                description="\n".join(words),
            )
        else:
            words = [
                self.bot.cache.fuzzy_ac.most_probable(word, distance=2)
                for word in word_or_phrase.split()
            ]
            embed = ctx.embed(
                description=" ".join(words),
            )

        await ctx.reply(embed=embed)


def format_pos_tags(
    word_tagging: list[tuple[str, str]],
    tag_map: dict[str, str],
) -> None:
    # first, what the tags mean
    tags = list(tag_map.keys())
    intro = "\n".join(
        f"{ANSI[POS_COLORS[tag]]}{f"{tags.index(tag)+1}.":<3}{ANSI["reset"]} {ANSI[POS_COLORS[tag]]}[{tag:<4}]{ANSI["reset"]} {ANSI["grey"]}{desc}{ANSI["reset"]}"
        for tag, desc in tag_map.items()
    )

    body = " ".join(
        f"{ANSI[POS_COLORS[tag]]}{word}{ANSI["reset"]}" for word, tag in word_tagging
    )

    # add a row of numbers below the start of each word, pointing to the number of the tag
    # spacing array is the number of the tag and then the number of spaces after
    # ie
    # rushmore
    # 4
    # is (4, 7, NNP)
    spacing = []
    for word, tag in word_tagging:
        tag_num = tags.index(tag) + 1
        spacing.append((len(word), tag_num, tag))

    # add the numbers to the definition
    definitions = []

    for wordlen, num, tag in spacing:
        spacing = wordlen - len(str(num))
        tag_color = ANSI[POS_COLORS[tag]]
        string = f"{tag_color}{num}{ANSI['reset']}{' ' * spacing}"
        if wordlen >= len(str(num)):
            string += " "
        definitions.append(string)

    return f"{intro}\n\n{body}\n{"".join(definitions)}"


class AfterTranslateView(VanirView):
    def __init__(
        self,
        ctx: VanirContext,
        from_lang_code: str,
        to_lang_code: str,
        text: str,
    ) -> None:
        super().__init__(ctx.bot, user=ctx.author)
        self.ctx = ctx
        self.from_lang_code = from_lang_code
        self.to_lang_code = to_lang_code
        self.text = text

        self.add_item(
            RepeatTranslateSelect(from_lang_code, to_lang_code, text),
        )


class RepeatTranslateSelect(discord.ui.Select[AfterTranslateView]):
    def __init__(
        self,
        from_lang_code: str,
        to_lang_code: str,
        text: str,
    ) -> None:
        options = [
            discord.SelectOption(
                label=lang,
                value=lang,
                default=lang == to_lang_code,
            )
            for lang, code in LANGUAGE_NAME_MAP.items()
            if code != from_lang_code
        ][:25]
        super().__init__(
            placeholder="Select a language to translate to",
            options=options,
        )
        self.from_lang_code = from_lang_code
        self.to_lang_code = to_lang_code
        self.text = text

    async def callback(self, itx: discord.Interaction) -> None:
        await itx.message.delete()
        translate = self.view.ctx.bot.get_command("translate")
        await self.view.ctx.invoke(
            translate,
            target_lang=self.values[0],
            text=self.text,
            source_lang=self.to_lang_code,
        )


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Language(bot))
