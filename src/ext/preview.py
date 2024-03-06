import io
from typing import Any
import discord
from discord import Interaction
from discord.ext import commands
from src.types.command import ModalField, VanirCog, VanirModal, VanirView
from src.constants import ANSI, ANSI_EMOJIS

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
        await ctx.reply(embed=embed, view=view)


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
        style=discord.ButtonStyle.success,
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
        label="Title", emoji="\N{Name Badge}", style=discord.ButtonStyle.blurple, row=0
    )
    async def set_title(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx,
            "Set Title",
            fields=[ModalField("Title Text")],
        )
        self.embed.title = values[0]
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Description",
        emoji="\N{Speech Balloon}",
        style=discord.ButtonStyle.blurple,
        row=0,
    )
    async def set_description(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx,
            "Set Description",
            fields=[ModalField("Description Text", style=discord.TextStyle.long)],
        )
        self.embed.description = values[0]
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Add Field",
        emoji="\N{Heavy Plus Sign}",
        style=discord.ButtonStyle.success,
        row=0,
    )
    async def add_field(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx,
            "Add Field",
            fields=[
                ModalField("Field Name"),
                ModalField("Field Value", required=False),
                ModalField("Inline?", required=False, default="No"),
            ],
        )
        self.embed.add_field(
            name=values[0],
            value=values[1],
            inline=values[2].lower() in ("yes", "y", "true", "ok"),
        )
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Remove Field",
        emoji="\N{Cross Mark}",
        style=discord.ButtonStyle.danger,
        row=0,
    )
    async def remove_field(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx, "Remove Field", fields=[ModalField("Field Name to Remove")]
        )
        before = self.embed.fields.copy()
        self.embed.clear_fields()
        for field in before:
            if field.name != values[0]:
                self.embed.add_field(
                    name=field.name, value=field.value, inline=field.inline
                )

        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Color",
        emoji="\N{Artist Palette}",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def set_color(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx,
            "Set Embed Color",
            fields=[ModalField("Enter Color as `#HEXDEC` or `rgb(r, g, b)")],
        )
        self.embed.color = discord.Color.from_str(values[0])
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Thumbnail",
        emoji="\N{Camera}",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def set_thumbnail(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx, "Set Thumbnail", fields=[ModalField("Enter Thumbnail URL")]
        )
        self.embed.set_thumbnail(url=values[0])
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Image",
        emoji="\N{Frame with Picture}",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def set_image(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx, "Set Image", fields=[ModalField("Enter Image URL")]
        )
        self.embed.set_image(url=values[0])
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Footer",
        emoji="\N{Small Blue Diamond}",
        style=discord.ButtonStyle.blurple,
        row=2,
    )
    async def set_footer(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx,
            title="Set Footer",
            fields=[
                ModalField("Enter Footer Text"),
                ModalField("Enter Footer Icon URL", required=False),
            ],
        )
        self.embed.set_footer(text=values[0], icon_url=values[1])
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Author",
        emoji="\N{Writing Hand}",
        style=discord.ButtonStyle.blurple,
        row=2,
    )
    async def set_author(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx,
            "Set Author",
            fields=[
                ModalField("Enter Author Name"),
                ModalField("Enter Author Icon URL", required=False),
                ModalField("Enter Author URL", required=False),
            ],
        )
        self.embed.set_author(name=values[0], icon_url=values[1], url=values[2])
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="URL",
        emoji="\N{Globe with Meridians}",
        style=discord.ButtonStyle.grey,
        row=2,
    )
    async def set_url(self, itx: discord.Interaction, button: discord.Button):
        values = await self._generate_modal(
            itx,
            "Set URL",
            fields=[ModalField("Enter Embed URL", style=discord.TextStyle.long)],
        )
        self.embed.url = values[0]
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Send",
        emoji="\N{Envelope with Downwards Arrow Above}",
        style=discord.ButtonStyle.success,
        row=2,
    )
    async def send(self, itx: discord.Interaction, button: discord.Button):
        if itx.message is not None:  # not ephemeral
            await itx.message.delete()
        await itx.response.defer()
        await itx.channel.send(embed=self.embed, view=None)

    async def _generate_modal(
        self, itx: discord.Interaction, title: str, fields: list[ModalField]
    ):
        modal = BasicInput(self.embed, title=title)

        for field in fields:
            item = discord.ui.TextInput(
                style=field.style,
                label=field.label,
                default=field.default,
                placeholder=field.placeholder,
                required=field.required,
            )
            modal.add_item(item)

        await itx.response.send_modal(modal)
        if await modal.wait():
            return

        children: list[discord.TextInput] = modal.children  # type: ignore

        return list(c.value for c in children)


class BasicInput(discord.ui.Modal):
    def __init__(self, embed: discord.Embed, title: str):
        super().__init__(title=title, timeout=None)
        self.embed = embed

    async def on_submit(self, itx: Interaction, /) -> None:
        await itx.response.defer()


async def setup(bot: Vanir):
    await bot.add_cog(Preview(bot))
