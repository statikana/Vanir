from enum import Enum
from src.types.command import VanirCog, VanirContext, vanir_group, Vanir
from discord.ext import commands

from env import WAIFU_IM_API_TOKEN


class TagName(Enum):
    def __init__(self, tag: str):
        try:
            super().__init__(tag)
        except ValueError:
            return None
        
    waifu = "waifu"
    maid = "main"
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



class Waifu(VanirCog):
    """Prety self-explanatory"""
    
    @vanir_group(aliases=["wf"])
    async def waifu(self, ctx: VanirContext, *, args: str):
        """Prety self-explanatory"""
        if args:
            tags = args.split()
            if len(tags) == 1:
                sfw, nsfw = args, None
            elif len(tags) == 2:
                sfw, nsfw = tags
            else:
                raise commands.TooManyArguments(f"Expected at most 2, got {len(tags)}")
            await ctx.invoke(self.get, sfw_tags=sfw, nsfw_tags=nsfw)
        else:
            await ctx.invoke(self.get, sfw_tags=None, nsfw_tags=None)
    
    
    @waifu.command()
    async def tags(self, ctx: VanirContext, show_nsfw: bool = False):
        response = await self.bot.session.get("https://api.waifu.im/tags?full=1")
        response.raise_for_status()
        
        data = await response.json()
        
        tags: list[dict[str, int | str | bool]] = data["versatile"]
        if show_nsfw:
            tags.extend(data["nsfw"])
        
        embed = ctx.embed(
            title="All waifu.im tags"
        )
        for tag in tags:
            embed.add_field(
                name=tag["name"],
                value=f"*{tag["description"]}*\n[ID: `{tag["tag_id"]}`, NSFW: `{tag["is_nsfw"]}`]",
                inline=True
            )
        
        await ctx.reply(embed=embed)
    
    @waifu.command()
    async def get(
        self,
        ctx: VanirContext,
        included_tags: str = commands.param(
            description="Comma-separated list of tags to include in the search [see \\wf tags]",
            default=""
        ),
        excluded_tags: str = commands.param(
            description="Comma-separated list of tags to exclude from the search [see \\wf tags]",
            default=""
        ),
        gif: bool = commands.param(
            description="Whether to get a gif instead of an image",
            default=False
        )        
    ):
        """Gets you a waifu image from waifu.im. For valid tags, see \\wf tags for tags"""
        inc, exc = included_tags.split(","), excluded_tags.split(",")
        
        if not all(TagName(tag) for tag in inc):
            raise commands.BadArgument("Invalid tag"
        
        url = "https://api.waifu.im/search"
        headers = {
            "Authorization": f"Bearer {WAIFU_IM_API_TOKEN}"
        }
        params = {
            
        }
        
        
        
async def setup(bot: Vanir):
    await bot.add_cog(Waifu(bot))