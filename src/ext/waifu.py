import datetime
from dataclasses import dataclass
from enum import Enum
from pprint import pprint
from typing import Generator

import discord
from discord.ext import commands

from src.constants import EMOJIS
from src.env import WAIFU_IM_API_TOKEN
from src.types.command import (
    AcceptItx,
    CloseButton,
    Vanir,
    VanirCog,
    VanirContext,
    VanirView,
    vanir_group,
)
from src.util.format import fmt_dict, fmt_size


class Waifu(VanirCog):
    """Prety self-explanatory"""

    emoji = str(EMOJIS["waifuim"])

    @vanir_group(aliases=["wf"])
    async def waifu(
        self,
        ctx: VanirContext,
        included_tags: str = commands.param(
            description="Comma-separated list of tags to include in the search [see `\\wf tags`]",
            default="",
        ),
        excluded_tags: str = commands.param(
            description="Comma-separated list of tags to exclude from the search [see `\\wf tags`]",
            default="",
        ),
        gif: bool = commands.param(
            description="Whether to get a gif instead of an image", default=False
        ),
        only_nsfw: bool = commands.param(
            description="Whether to get a NSFW image", default=False
        ),
    ):
        """Prety self-explanatory [default: `\\wf get ...`]"""
        await ctx.invoke(
            self.get,
            included_tags=included_tags,
            excluded_tags=excluded_tags,
            gif=gif,
            only_nsfw=only_nsfw,
        )

    @waifu.command()
    async def tags(self, ctx: VanirContext):
        """Get a list of all available tags on waifu.im"""
        response = await self.bot.session.get("https://api.waifu.im/tags?full=1")
        response.raise_for_status()

        data = await response.json()

        tags = [FullTag._from_dict(tag) for tag in data["versatile"]]
        tags.extend([FullTag._from_dict(tag) for tag in data["nsfw"]])

        embed = ctx.embed(
            title="Waifu.im Tags",
        )
        for tag in tags:
            embed.add_field(
                name=f"{tag.name} | ID: `{tag.tag_id}`{' | :underage:`NSFW`' if tag.is_nsfw else ''}",
                value=f"> {tag.description}",
                inline=False,
            )

        await ctx.reply(embed=embed)

    @waifu.command()
    async def get(
        self,
        ctx: VanirContext,
        included_tags: str = commands.param(
            description="Comma-separated list of tags to include in the search [see `\\wf tags`]",
            default="",
        ),
        excluded_tags: str = commands.param(
            description="Comma-separated list of tags to exclude from the search [see `\\wf tags`]",
            default="",
        ),
        gif: bool = commands.param(
            description="Whether to get a gif instead of an image", default=False
        ),
        only_nsfw: bool = commands.param(
            description="Whether to get a NSFW image", default=False
        ),
    ):
        """Gets you a waifu image from waifu.im. See `\\wf tags` for a list of available tags."""
        embed, view = await get_results(
            ctx, included_tags, excluded_tags, gif, only_nsfw
        )
        await ctx.reply(embed=embed, view=view)


async def get_results(
    ctx: VanirContext,
    included_tags: str,
    excluded_tags: str,
    gif: bool,
    only_nsfw: bool,
):
    inc, exc = (
        list(extract_tags(included_tags or "")),
        list(extract_tags(excluded_tags or "")),
    )
    only_nsfw = only_nsfw or (all(tag.is_nsfw for tag in inc) and len(inc) > 0)

    if (only_nsfw or any(tag.is_nsfw for tag in inc)) and not ctx.channel.is_nsfw():
        raise commands.NSFWChannelRequired(ctx.channel)

    url = "https://api.waifu.im/search"
    headers = {"Authorization": f"Bearer {WAIFU_IM_API_TOKEN}"}
    query = f"gif={gif}&is_nsfw={only_nsfw}"
    for tag in inc:
        query += f"&included_tags={tag.name}"
    for tag in exc:
        query += f"&excluded_tags={tag.name}"

    response = await ctx.bot.session.get(f"{url}?{query}", headers=headers)
    json = await response.json()
    if "detail" in json:
        raise ValueError(json["detail"] + f"\nuri: {response.url}")
    image_json = json["images"][0]
    image = WaifuData._from_dict(image_json)

    embed = ctx.embed()
    embed.set_image(url=image.url)
    embed.color = discord.Color.from_str(image.dominant_color)

    footer_text = f"tags: {', '.join(tag.name for tag in image.tags)}"
    if image.artist is not None:
        footer_text += f" | artist: {image.artist.name}"
    if only_nsfw:
        footer_text += " | NSFW Only"
    else:
        if any(tag.is_nsfw for tag in inc):
            footer_text += " | NSFW Permitted"
    embed.set_footer(text=footer_text, icon_url="https://www.waifu.im/favicon.ico")

    view = WaifuDataView(ctx, image, inc, exc, gif, only_nsfw)
    return embed, view


class TagNames(Enum):
    waifu = "waifu"
    maid = "maid"
    marin_kitagawa = "marin-kitagawa"
    mori_calliope = "mori-calliope"
    raiden_shogun = "raiden-shogun"
    oppai = "oppai"
    selfies = "selfies"
    uniform = "uniform"
    kamisato_ayaka = "kamisato-ayaka"
    ero = "ero"
    ass = "ass"
    hentai = "hentai"
    milf = "milf"
    oral = "oral"
    paizuri = "paizuri"
    ecchi = "ecchi"


@dataclass
class FullTag:
    tag_id: int
    name: str
    description: str
    is_nsfw: bool

    @classmethod
    def _from_dict(cls, data: dict):
        return FullTag(
            tag_id=data["tag_id"],
            name=data["name"],
            description=data["description"],
            is_nsfw=data["is_nsfw"],
        )


class TagData:
    maid = FullTag(
        "13",
        "maid",
        "Cute womans or girl employed to do domestic work in their working uniform.",
        False,
    )
    waifu = FullTag("12", "waifu", "A female anime/manga character.", False)
    marin_kitagawa = FullTag(
        "5",
        "marin-kitagawa",
        "One of two main protagonists (alongside Wakana Gojo) in the anime and manga series My Dress-Up Darling.",
        False,
    )
    mori_calliope = FullTag(
        "14",
        "mori-calliope",
        "Mori Calliope is an English Virtual YouTuber (VTuber) associated with hololive as part of its first-generation English branch of Vtubers.",
        False,
    )
    raiden_shogun = FullTag(
        "15",
        "raiden-shogun",
        "Genshin Impact's Raiden Shogun is a fierce lady in the Genshin ranks.",
        False,
    )
    oppai = FullTag("7", "oppai", "Girls with large breasts", False)
    selfies = FullTag("10", "selfies", "A photo-like image of a waifu.", False)
    uniform = FullTag(
        "11", "uniform", "Girls wearing any kind of uniform, cosplay etc... ", False
    )
    kamisato_ayaka = FullTag(
        "17",
        "kamisato-ayaka",
        "Kamisato Ayaka is a playable Cryo character in Genshin Impact.",
        False,
    )
    ass = FullTag("1", "ass", "Girls with a large butt. ", True)
    hentai = FullTag("4", "hentai", "Explicit sexual content.", True)
    milf = FullTag("6", "milf", "A sexually attractive middle-aged woman.", True)
    oral = FullTag("8", "oral", "Oral sex content.", True)
    paizuri = FullTag(
        "9",
        "paizuri",
        "A subcategory of hentai that involves breast sex, also known as titty fucking.",
        True,
    )
    ecchi = FullTag(
        "2",
        "ecchi",
        "Slightly explicit sexual content. Show full to partial nudity. Doesn't show any genital.",
        True,
    )
    ero = FullTag(
        "3", "ero", "Any kind of erotic content, basically any nsfw image.", True
    )


@dataclass
class Artist:
    artist_id: int
    name: str
    patreon: str | None
    pixiv: str | None
    twitter: str | None
    deviant_art: str | None


@dataclass
class WaifuData:
    signature: str
    extension: str
    image_id: int
    favorites: int
    dominant_color: str
    source: str
    artist: Artist | None
    uploaded_at: datetime.datetime
    is_nsfw: bool
    width: int
    height: int
    byte_size: int
    url: str
    preview_url: str
    tags: list[FullTag]

    @classmethod
    def _from_dict(cls, data: dict[str, int | str | bool]) -> "WaifuData":
        kwargs = {
            "signature": data["signature"],
            "extension": data["extension"],
            "image_id": data["image_id"],
            "favorites": data["favorites"],
            "dominant_color": data["dominant_color"],
            "source": data["source"],
            "uploaded_at": datetime.datetime.fromisoformat(data["uploaded_at"]),
            "is_nsfw": data["is_nsfw"],
            "width": data["width"],
            "height": data["height"],
            "byte_size": data["byte_size"],
            "url": data["url"],
            "preview_url": data["preview_url"],
            "tags": [
                FullTag(
                    tag_id=tag["tag_id"],
                    name=tag["name"],
                    description=tag["description"],
                    is_nsfw=tag["is_nsfw"],
                )
                for tag in data["tags"]
            ],
        }
        if data["artist"] is not None:
            artist = data["artist"]
            kwargs["artist"] = Artist(
                artist_id=artist["artist_id"],
                name=artist["name"],
                patreon=artist["patreon"],
                pixiv=artist["pixiv"],
                twitter=artist["twitter"],
                deviant_art=artist["deviant_art"],
            )
        else:
            kwargs["artist"] = None
        return cls(**kwargs)


class WaifuDataView(VanirView):
    def __init__(
        self,
        ctx: VanirContext,
        data: WaifuData,
        inc: list[FullTag],
        exc: list[FullTag],
        gif: bool,
        only_nsfw: bool,
    ):
        super().__init__(ctx.bot, accept_itx=AcceptItx.ANY)
        self.ctx = ctx
        self.data = data
        self.inc = inc
        self.exc = exc
        self.gif = gif
        self.only_nsfw = only_nsfw

        self.artist.disabled = data.artist is None

        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                url=data.preview_url,
                label="Preview",
                emoji="\N{FRAME WITH PICTURE}",
            )
        )

        close_button = CloseButton()
        close_button.row = 1
        self.add_item(close_button)

    @discord.ui.button(
        label="New",
        emoji="\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}",
        style=discord.ButtonStyle.success,
    )
    async def new(self, itx: discord.Interaction, button: discord.ui.Button):
        embed, view = await get_results(
            self.ctx,
            ",".join(t.name for t in self.inc),
            ",".join(t.name for t in self.exc),
            self.gif,
            self.only_nsfw,
        )
        await itx.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="Artist", emoji="\N{ARTIST PALETTE}", style=discord.ButtonStyle.blurple
    )
    async def artist(self, itx: discord.Interaction, button: discord.ui.Button):
        embed = self.ctx.embed(
            title=f"Artist: {self.data.artist.name}",
            description=f"[Waifu.im Artist ID: {self.data.artist.artist_id}]",
        )

        platform_str = ""
        for name, url in (
            ("patreon", self.data.artist.patreon),
            ("pixiv", self.data.artist.pixiv),
            ("x", self.data.artist.twitter),
            ("deviant_art", self.data.artist.deviant_art),
        ):
            if url is not None:
                emoji = str(EMOJIS[name])
                platform_str += f"{emoji} [{name.replace("_", " ").title()}]({url})\n"

        embed.add_field(
            name="Platforms",
            value=platform_str or "No platforms found",
        )
        embed.set_thumbnail(url=self.data.url)

        await itx.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="Image Data",
        emoji="\N{CARD INDEX}",
        style=discord.ButtonStyle.grey,
    )
    async def image_data(self, itx: discord.Interaction, button: discord.ui.Button):
        data = {
            "Image ID": f"`{self.data.image_id}`",
            "\\# Favorites": f"{self.data.favorites:,}",
            "Source": self.data.source,
            "Uploaded At": f"{self.data.uploaded_at:%x}",
            "Is NSFW": self.data.is_nsfw,
            "Dimensions": f"{self.data.width}x{self.data.height}",
            "File Size": fmt_size(self.data.byte_size),
            "File Type": self.data.extension[1:].upper(),
        }
        description = fmt_dict(data)
        embed = self.ctx.embed(title="Image Data", description=description)
        embed.set_thumbnail(url=self.data.url)
        await itx.response.send_message(embed=embed, ephemeral=True)


def extract_tags(tag_string: str) -> Generator[FullTag, None, None]:
    if not tag_string:
        return
    tags = tag_string.split(",")
    try:
        for tag in tags:
            obj = TagNames(tag)
            full_tag = getattr(TagData, obj.name)
            yield full_tag
    except (TypeError, ValueError, AttributeError) as e:
        print(e)
        raise ValueError(f"Invalid tag: {tag}") from e


async def setup(bot: Vanir):
    await bot.add_cog(Waifu(bot))
