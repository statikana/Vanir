

import discord
from src.types.core import Vanir, VanirContext
from src.types.command import VanirCog
from src.util.command import cog_hidden


@cog_hidden
class Menus(VanirCog):
    def __init__(self, bot: Vanir) -> None:
        self.bot = bot
        self.translate = discord.app_commands.ContextMenu(
            name="Translate to English",
            type=discord.AppCommandType.message,
            nsfw=False,
            callback=self.translate_callback,
        )
        self.bot.tree.add_command(self.translate)
    
    async def translate_callback(self, itx: discord.Interaction, msg: discord.Message) -> None:
        ctx = await VanirContext.from_interaction(itx)
        translate = self.bot.get_command("translate")
        await ctx.invoke(translate, text=msg.content, source_lang="AUTO")


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Menus(bot))
        