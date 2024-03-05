import io
from typing import Any
import discord
from discord import Interaction
from discord._types import ClientT
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
        start_text: str = commands.param(description="Starting text", default=""),
    ):
        """ANSI Color codes creating and preview"""
        default = start_text or "<press [Add] to get started>\n<or select a color>"
        embed = ctx.embed(description=f"```ansi\n{default}\n```")
        embed.add_field(
            name="\N{Warning Sign} Discord does not support ANSI on mobile.", value=""
        )
        view = ANSIView(ctx, embed, start_text)
        await ctx.reply(embed=embed, view=view)

    @vanir_command()
    async def embed(
        self,
        ctx: VanirContext,
    ):
        embed = discord.Embed(title="Example Title")
        view = EmbedView(ctx, embed)
        await ctx.send(embed=embed, view=view)


class ANSIView(VanirView):
    def __init__(self, ctx: VanirContext, embed: discord.Embed, start: str = ""):
        color_select = ColorSelect(ctx)
        super().__init__(ctx.bot, user=ctx.author)
        self.add_item(color_select)

        self.add_item(
            discord.ui.Button(
                label="How?",
                emoji="\N{White Question Mark Ornament}",
                row=1,
                url="https://gist.github.com/kkrypt0nn/a02506f3712ff2d1c8ca7c9e0aed7c06",
            )
        )

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
        row=1,
    )
    async def add_text(self, itx: discord.Interaction, button: discord.Button):
        modal = AddTextModal(self.ctx.bot)
        await itx.response.send_modal(modal)

        if await modal.wait():  # timed out
            return

        self.internal_text += modal.text_input.value + " "
        await itx.message.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(
        label="Edit", emoji="\N{Pencil}", style=discord.ButtonStyle.blurple, row=1
    )
    async def edit_text(self, itx: discord.Interaction, button: discord.Button):
        modal = EditTextModal(self.ctx.bot, self.internal_text)
        await itx.response.send_modal(modal)

        if await modal.wait():
            return

        self.internal_text = modal.text_input.value
        await itx.message.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(
        label="Raw", emoji="\N{Electric Plug}", style=discord.ButtonStyle.gray, row=1
    )
    async def get_raw(self, itx: discord.Interaction, button: discord.Button):
        file = discord.File(io.BytesIO(self.internal_text.encode()))
        await itx.response.send_message(
            f"```\n{self.internal_text}\n```", file=file, ephemeral=True
        )


class ColorSelect(discord.ui.Select[ANSIView]):
    def __init__(self, ctx: VanirContext):
        colors = [
            discord.SelectOption(
                label=name, value=seq, default=name == "white", emoji=ANSI_EMOJIS[name]
            )
            for name, seq in ANSI.items()
            if name != "reset"
        ]
        super().__init__(placeholder="Please choose a color", options=colors, row=0)
        self.ctx = ctx

    async def callback(self, itx: discord.Interaction):
        self.view.internal_text += self.values[0]
        embed = self.view.make_embed()

        for o in self.options:
            o.default = False

        new_default: discord.SelectOption = discord.utils.get(
            self.options, value=self.values[0]
        )
        new_default.default = True

        await itx.response.edit_message(embed=embed, view=self.view)


class AddTextModal(VanirModal, title="Add Text"):
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
        label="Edit Text", style=discord.TextStyle.paragraph
    )

    async def on_submit(self, itx: discord.Interaction) -> None:
        await itx.response.defer()


class EmbedView(VanirView):
    def __init__(self, ctx: VanirContext, embed: discord.Embed):
        super().__init__(ctx.bot, user=ctx.author)
        self.embed = embed

    @discord.ui.button(
        label="Set Title", emoji="\N{Name Badge}", style=discord.ButtonStyle.blurple
    )
    async def set_title(self, itx: discord.Interaction, button: discord.Button):
        await itx.response.send_modal(EmbedSetTitleModal(self.embed))

    @discord.ui.button(
        label="Set Description",
        emoji="\N{Speech Balloon}",
        style=discord.ButtonStyle.blurple,
    )
    async def set_description(self, itx: discord.Interaction, button: discord.Button):
        await itx.response.send_modal(EmbedSetDescriptionModal(self.embed))

    @discord.ui.button(
        label="Add Field",
        emoji="\N{Heavy Plus Sign}",
        style=discord.ButtonStyle.success,
    )
    async def add_field(self, itx: discord.Interaction, button: discord.Button):
        await itx.response.send_modal(EmbedAddFieldModal(self.embed))

    @discord.ui.button(
        label="Remove Field", emoji="\N{Cross Mark}", style=discord.ButtonStyle.danger
    )
    async def remove_field(self, itx: discord.Interaction, button: discord.Button):
        await itx.response.send_modal(EmbedRemoveFieldModal(self.embed))

    @discord.ui.button(
        label="Set Color",
        emoji="\N{Artist Palette}",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def set_color(self, itx: discord.Interaction, button: discord.Button):
        await itx.response.send_modal(EmbedSetColorModal(self.embed))

    @discord.ui.button(
        label="Set URL",
        emoji="\N{Globe with Meridians}",
        style=discord.ButtonStyle.grey,
        row=1,
    )
    async def set_url(self, itx: discord.Interaction, button: discord.Button):
        await itx.response.send_modal(EmbedSetURLModal(self.embed))

    @discord.ui


class BasicInput(discord.ui.Modal):
    def __init__(self, embed: discord.Embed):
        super().__init__()
        self.embed = embed


class EmbedSetTitleModal(BasicInput, title="Enter Embed Title"):
    text_input = discord.ui.TextInput(label="Title", style=discord.TextStyle.short)

    async def on_submit(self, itx: discord.Interaction):
        self.embed.title = self.text_input.value
        await itx.response.edit_message(embed=self.embed)


class EmbedSetDescriptionModal(BasicInput, title="Enter Embed Description"):
    text_input = discord.ui.TextInput(
        label="Description", style=discord.TextStyle.paragraph
    )

    async def on_submit(self, itx: discord.Interaction):
        self.embed.description = self.text_input.value
        await itx.response.edit_message(embed=self.embed)


class EmbedAddFieldModal(BasicInput, title="Enter Field Data"):
    name = discord.ui.TextInput(label="Name", style=discord.TextStyle.short)
    value = discord.ui.TextInput(
        label="Value", style=discord.TextStyle.paragraph, required=False
    )
    inline = discord.ui.TextInput(
        label="Inline",
        style=discord.TextStyle.short,
        placeholder="Yes / No",
        default="No",
    )

    async def on_submit(self, itx: discord.Interaction):
        self.embed.add_field(
            name=self.name.value,
            value=self.value.value,
            inline=self.inline.value.lower() in ("yes", "y", "true", "ok"),
        )
        await itx.response.edit_message(embed=self.embed)


class EmbedRemoveFieldModal(BasicInput, title="Remove Field"):
    text_input = discord.ui.TextInput(label="Enter the name of the field to be removed")

    async def on_submit(self, itx: Interaction):
        before = self.embed.fields.copy()
        self.embed.clear_fields()
        [
            self.embed.add_field(name=f.name, value=f.value, inline=f.inline)
            for f in before
            if f.name != self.text_input.value
        ]
        await itx.response.edit_message(embed=self.embed)


async def setup(bot: Vanir):
    await bot.add_cog(Preview(bot))
