import io
from typing import Any
import discord
from discord.ext import commands
from src.types.command import VanirCog, VanirModal, VanirView
from src.constants import ANSI, ANSI_CODES, ANSI_EMOJIS

from src.types.core import Vanir, VanirContext
from src.util.command import vanir_command


class Preview(VanirCog):
    @vanir_command()
    async def ansi(
        self,  
        ctx: VanirContext, 
        start_text: str = commands.param(description="Starting text", default="")
    ):
        """ANSI Color codes creating and preview"""
        embed = ctx.embed(description=f"```ansi\n{start_text}\n```")
        view = ANSIView(ctx, embed, start_text)
        await ctx.reply(embed=embed, view=view)


class ANSIView(VanirView):
    def __init__(self, ctx: VanirContext, embed: discord.Embed, start: str = ""):
        color_select = ColorSelect(ctx)
        super().__init__(ctx.bot, user=ctx.author)
        self.add_item(color_select)

        self.ctx = ctx
        self._embed = embed
        self.internal_text = start

    def make_embed(self):
        embed = self._embed
        embed.description = f"```ansi\n{self.internal_text}\n```"
        return self._embed
    
    @discord.ui.button(
        label="Add", 
        emoji="\N{Heavy Plus Sign}", 
        style=discord.ButtonStyle.blurple,
        row=1
    )
    async def add_text(self, itx: discord.Interaction, button: discord.Button):
        modal = AddTextModal(self.ctx.bot)
        await itx.response.send_modal(modal)

        if await modal.wait():  # timed out
            return
        
        self.internal_text += modal.text_input.value + " "
        await itx.message.edit(embed=self.make_embed(), view=self)
    
    @discord.ui.button(
        label="Edit", 
        emoji="\N{Pencil}", 
        style=discord.ButtonStyle.blurple,
        row=1
    )
    async def edit_text(self, itx: discord.Interaction, button: discord.Button):
        modal = EditTextModal(self.ctx.bot, self.internal_text)
        await itx.response.send_modal(modal)

        if await modal.wait():
            return
        
        self.internal_text = modal.text_input.value
        await itx.message.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(
        label="Raw",
        emoji="\N{Electric Plug}",
        style=discord.ButtonStyle.gray,
        row=1
    )
    async def get_raw(self, itx: discord.Interaction, button: discord.Button):
        file = discord.File(io.BytesIO(self.internal_text.encode()))
        await itx.response.send_message(f"```\n{self.internal_text}\n```", file=file, ephemeral=True)

class ColorSelect(discord.ui.Select[ANSIView]):
    def __init__(self, ctx: VanirContext):
        colors = [
            discord.SelectOption(
                label=name, 
                value=seq, 
                default=name=="whihte", 
                emoji=ANSI_EMOJIS[name]
            ) for name, seq in ANSI.items()
            if name
        ]
        super().__init__(
            placeholder="Please choose a color",
            options=colors,
            row=0
        )
        self.ctx = ctx

    
    async def callback(self, itx: discord.Interaction):
        self.view.internal_text += self.values[0]
        embed = self.view.make_embed()

        for o in self.options:
            o.default = False

        new_default: discord.SelectOption = discord.utils.get(self.options, value=self.values[0])
        new_default.default = True

        await itx.response.edit_message(embed=embed, view=self.view)
    
    
class AddTextModal(VanirModal, title="Add Text"):
    def __init__(self, bot: Vanir):
        super().__init__(bot)

    text_input = discord.ui.TextInput(
        label="Text to Add",
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, itx: discord.Interaction) -> None:
        await itx.response.defer()


class EditTextModal(VanirModal, title="Edit Text"):
    def __init__(self, bot: Vanir, current: str):
        self.text_input.default = current
        super().__init__(bot)

    text_input = discord.ui.TextInput(
        label="Edit Text",
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, itx: discord.Interaction) -> None:
        await itx.response.defer()


async def setup(bot: Vanir):
    await bot.add_cog(Preview(bot))