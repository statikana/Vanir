import discord
from discord.ext import commands

from discord import app_commands

from src.types.command import vanir_command, VanirCog, vpar, VanirView
from src.types.core import VanirContext, Vanir
from src.types.util import langcode_autocomplete, LANGUAGE_INDEX


class Language(VanirCog):

    @vanir_command()
    async def define(self, ctx: VanirContext, *, term: str):
        url = "https://api.dictionaryapi.dev/api/v2/entries/en/"
        response = await self.bot.session.get(url + term)
        response.raise_for_status()

        json = (await response.json())[0]
        title = f"{term}"

        if json["phonetic"]:
            title += f" [{json['phonetic']}]"

        embed = ctx.embed(title, url=json["sourceUrls"][0])
        view = VanirView()

        for regional_phonetic in json["phonetics"]:
            if audio_file := regional_phonetic["audio"]:
                view.add_item(
                    discord.ui.Button(
                        style=discord.ButtonStyle.url,
                        label=f"{audio_file[audio_file.rfind('-')+1:audio_file.rfind('.')].upper()} Pronunciation",
                        emoji="\N{Speaker with Three Sound Waves}",
                        url=audio_file,
                    )
                )

        def format_def(index, definition):
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
                formatted = format_def(i, d)
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
                name=f"as ***{meaning['partOfSpeech']}***", value=value, inline=False
            )

        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command()
    @app_commands.autocomplete(
        source_lang=langcode_autocomplete, target_lang=langcode_autocomplete
    )
    @commands.cooldown(2, 60, commands.BucketType.user)
    async def translate(
        self,
        ctx: VanirContext,
        *,
        text: str = vpar("The text to translate"),
        source_lang: str = vpar("The language to translate from", "AUTO"),
        target_lang: str = vpar("The language to translate to", "EN"),
    ):
        """Translates the text to `target_lang` - default is English"""
        if isinstance(source_lang, commands.Parameter):
            source_lang = source_lang.default
        if isinstance(target_lang, commands.Parameter):
            target_lang = target_lang.default

        source_lang = source_lang.upper()
        target_lang = target_lang.upper()
        text = text[:100]

        json = {
            "text": [text],
            "target_lang": target_lang,
        }
        if source_lang != "AUTO":
            json["source_lang"] = source_lang

        if source_lang not in LANGUAGE_INDEX and source_lang != "AUTO":
            raise ValueError(
                f"{source_lang} is not a valid language code. Please utilize the autocomplete"
            )
        if target_lang not in LANGUAGE_INDEX:
            raise ValueError(
                f"{target_lang} is not a valid language code. Please utilize the autocomplete"
            )

        response = await self.bot.session.deepl("/translate", json=json)
        response.raise_for_status()
        json = await response.json()

        tsl = json["translations"][0]

        source = LANGUAGE_INDEX[tsl["detected_source_language"]]
        target = LANGUAGE_INDEX[target_lang]

        embed = ctx.embed(title=f"{source} -> {target}")
        embed.add_field(name=f"{source} - Original", value=text, inline=False)
        embed.add_field(name=f"{target} - Translated", value=tsl["text"], inline=False)
        await ctx.send(embed=embed)


async def setup(bot: Vanir):
    await bot.add_cog(Language(bot))
