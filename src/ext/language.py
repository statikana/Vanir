import discord
from discord import app_commands
from discord.ext import commands

from src.constants import (
    LANGUAGE_CODE_MAP,
    LANGUAGE_CODES,
    LANGUAGE_NAME_MAP,
    LANGUAGE_NAMES,
)
from src.types.command import VanirCog, VanirView, vanir_command
from src.types.core import Vanir, VanirContext
from src.util.command import langcode_autocomplete


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
            fmt_definition = f"**{i + 1}.** {discord.utils.escape_markdown(definition['definition'])}"
            if "example" in definition:
                fmt_definition += (
                    f"\n\t> *{discord.utils.escape_markdown(definition['example'])}*"
                )
            return fmt_definition

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
            default=None
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
        
        print("from", source_lang)
        print("to", target_lang)
        print("text", text)    

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
        print(json)
        response = await self.bot.session.deepl("/translate", json=json)
        response.raise_for_status()
        print(await response.json())
        tsl = (await response.json())["translations"][0]

        source = LANGUAGE_CODE_MAP[tsl["detected_source_language"]]
        target = LANGUAGE_CODE_MAP[target_lang]

        embed = ctx.embed(description=tsl["text"])
        embed.set_footer(
            text=f"{source} -> {target}",
        )
        view = AfterTranslateView(ctx, tsl["detected_source_language"], target_lang, tsl["text"])
        await ctx.reply(embed=embed, view=view)


class AfterTranslateView(VanirView):
    def __init__(
        self,
        ctx: VanirContext,
        from_lang_code: str,
        to_lang_code: str,
        text: str,
    ):
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
        self,from_lang_code: str,
        to_lang_code: str,
        text: str,
    ):
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
    
    async def callback(self, itx: discord.Interaction):
        await itx.message.delete()
        translate = self.view.ctx.bot.get_command("translate")
        await self.view.ctx.invoke(translate, target_lang=self.values[0], text=self.text, source_lang=self.to_lang_code)
    


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Language(bot))
