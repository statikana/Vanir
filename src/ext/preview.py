import io
import json
from typing import Any

import discord
import sympy
from discord.ext import commands
from PIL import Image

from assets.color_db import COLOR_INDEX
from src.constants import ANSI, ANSI_EMOJIS
from src.types.command import VanirCog, VanirModal, VanirView, vanir_command
from src.types.core import Vanir, VanirContext
from src.util.ux import generate_modal


class Preview(VanirCog):
    """Formatting stuffs."""

    emoji = "\N{LEFT-POINTING MAGNIFYING GLASS}"

    @vanir_command()
    async def ansi(
        self,
        ctx: VanirContext,
        start_text: str = commands.param(description="Starting text", default=""),
    ) -> None:
        """ANSI Color codes creating and preview."""
        default = start_text or "<press [Add] to get started>\n<or select a color>"
        embed = ctx.embed(description=f"```ansi\n{default}\n```")
        embed.add_field(
            name="\N{WARNING SIGN} Discord does not support ANSI on mobile.",
            value="",
        )
        view = ANSIView(ctx, embed, start_text)
        await ctx.reply(embed=embed, view=view)

    @vanir_command()
    async def embed(
        self,
        ctx: VanirContext,
    ) -> None:
        """A simple embed builder."""
        embed = discord.Embed(title="Example Title")
        view = EmbedView(ctx, embed)
        await ctx.reply(embed=embed, view=view)

    @vanir_command(aliases=["ltx", "render", "l"])
    async def latex(
        self,
        ctx: VanirContext,
        *,
        latex: str = commands.param(description="LaTeX code to render"),
        use_math: bool = commands.param(
            description="Use math mode automatically",
            default=True,
        ),
        preambled: bool = commands.param(
            description="Automatically apply a simple preamble",
            default=True,
        ),
    ) -> None:
        """Render LaTeX code."""
        border_px = 10

        output = io.BytesIO()
        latex = latex.strip("` ").replace("\\\\", "\\").replace("\\n", "\n").strip()
        preamble = "\\documentclass{article}\n\\usepackage{amsmath}\n\\usepackage{amsfonts}\n\\usepackage{amssymb}\n\\pagestyle{empty}\n\\begin{document}"
        outline = "\\[ [[LATEX]] \\]" if use_math else "[[LATEX]]"
        frame = outline + "\n\\end{document}"
        latex = frame.replace("[[LATEX]]", latex)
        try:
            sympy.preview(
                latex.strip(),
                preamble=preamble if preambled else None,
                viewer="BytesIO",
                outputbuffer=output,
                fontsize=12,
                dvioptions=["-D", "400", "-T", "tight", "-z", "0"],
            )
        except ValueError as error:
            breaker = "\\r\\n\\r"
            index = str(error).rfind(breaker)
            index_end = str(error).rfind("<to be read again>")
            message = str(error)[index + len(breaker) : index_end]
            message = message.replace("\\n", "\n").replace("\\r", "\r")
            msg = f"Error in parsing LaTeX: {message}"
            raise ValueError(msg) from error
        output.seek(0)
        latex_img = Image.open(output)

        new = Image.new(
            "RGB",
            (latex_img.width + border_px * 2, latex_img.height + border_px * 2),
            (255, 255, 255),
        )
        new.paste(latex_img, (border_px, border_px))

        buf = io.BytesIO()
        new.save(buf, format="PNG")
        buf.seek(0)
        file = discord.File(buf, filename="latex.png")

        await ctx.reply(file=file)


class ANSIView(VanirView):
    def __init__(
        self,
        ctx: VanirContext,
        embed: discord.Embed,
        start: str = "",
    ) -> None:
        color_select = ColorSelect(ctx)
        super().__init__(ctx.bot, user=ctx.author)
        self.add_item(color_select)

        self.add_item(
            discord.ui.Button(
                label="How?",
                emoji="\N{WHITE QUESTION MARK ORNAMENT}",
                row=1,
                url="https://gist.github.com/kkrypt0nn/a02506f3712ff2d1c8ca7c9e0aed7c06",
            ),
        )

        self.ctx = ctx
        self._embed = embed
        self.internal_text = start

    def make_embed(self) -> discord.Embed:
        embed = self._embed
        embed.description = f"```ansi\n{self.internal_text}\n```"
        return self._embed

    @discord.ui.button(
        label="Add",
        emoji="\N{HEAVY PLUS SIGN}",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def add_text(self, itx: discord.Interaction, button: discord.Button) -> None:
        modal = AddTextModal(self.ctx.bot)
        await itx.response.send_modal(modal)

        if await modal.wait():  # timed out
            return

        self.internal_text += modal.text_input.value + " "
        await itx.message.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(
        label="Edit",
        emoji="\N{PENCIL}",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def edit_text(self, itx: discord.Interaction, button: discord.Button) -> None:
        modal = EditTextModal(self.ctx.bot, self.internal_text)
        await itx.response.send_modal(modal)

        if await modal.wait():
            return

        self.internal_text = modal.text_input.value
        await itx.message.edit(embed=self.make_embed(), view=self)

    @discord.ui.button(
        label="Raw",
        emoji="\N{ELECTRIC PLUG}",
        style=discord.ButtonStyle.gray,
        row=1,
    )
    async def get_raw(self, itx: discord.Interaction, button: discord.Button) -> None:
        file = discord.File(io.BytesIO(self.internal_text.encode()))
        await itx.response.send_message(
            f"```\n{self.internal_text}\n```",
            file=file,
            ephemeral=True,
        )


class ColorSelect(discord.ui.Select[ANSIView]):
    def __init__(self, ctx: VanirContext) -> None:
        colors = [
            discord.SelectOption(
                label=name,
                value=seq,
                default=name == "white",
                emoji=ANSI_EMOJIS[name],
            )
            for name, seq in ANSI.items()
            if name != "reset"
        ]
        super().__init__(placeholder="Please choose a color", options=colors, row=0)
        self.ctx = ctx

    async def callback(self, itx: discord.Interaction) -> None:
        self.view.internal_text += self.values[0]
        embed = self.view.make_embed()

        for o in self.options:
            o.default = False

        new_default: discord.SelectOption = discord.utils.get(
            self.options,
            value=self.values[0],
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
    def __init__(self, bot: Vanir, current: str) -> None:
        self.text_input.default = current
        super().__init__(bot)

    text_input = discord.ui.TextInput(
        label="Edit Text",
        style=discord.TextStyle.paragraph,
    )

    async def on_submit(self, itx: discord.Interaction) -> None:
        await itx.response.defer()


class EmbedView(VanirView):
    def __init__(self, ctx: VanirContext, embed: discord.Embed) -> None:
        super().__init__(ctx.bot, user=ctx.author)
        self.embed = embed
        self.ctx = ctx

        if ctx.guild is None:
            self.send_other.disabled = True

        self.remove_field.disabled = True
        self.edit_field.disabled = True

    @discord.ui.button(
        label="Edit:",
        style=discord.ButtonStyle.grey,
        disabled=True,
        row=0,
    )
    async def _header_edit(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        return

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.blurple, row=0)
    async def edit_embed(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        title, description, url, color = await generate_modal(
            itx,
            "Embed Content",
            fields=[
                # title
                discord.ui.TextInput(
                    label="Title",
                    placeholder="Up to 256 characters",
                    required=False,
                    max_length=256,
                    default=self.embed.title,
                ),
                discord.ui.TextInput(
                    label="Description",
                    placeholder="Up to 4096 characters",
                    required=False,
                    style=discord.TextStyle.paragraph,
                    max_length=4096,
                    default=self.embed.description,
                ),
                discord.ui.TextInput(
                    label="URL",
                    placeholder="Must be HTTP[S] format",
                    required=False,
                    default=self.embed.url,
                ),
                discord.ui.TextInput(
                    label="Color",
                    placeholder="Hex-code #FFFFFF, rbg(171, 255, 1), or a color name",
                    required=False,
                    default=f"rbg{self.embed.color.to_rgb()}"
                    if self.embed.color
                    else None,
                ),
            ],
        )
        self.embed.title = title
        self.embed.description = description
        self.embed.url = url
        try:
            color = discord.Color.from_str(color)
        except ValueError:
            if (fixed := color.lower().replace(" ", "")) in COLOR_INDEX:
                color = discord.Color.from_str(COLOR_INDEX[fixed][0])
            else:
                await itx.followup.send(
                    embed=discord.Embed(
                        color=discord.Color.red(),
                        description="Invalid color. Please use a valid hex, rbg, or .",
                    ),
                    ephemeral=True,
                )
                return

        self.embed.color = color
        try:
            await itx.followup.edit_message(itx.message.id, embed=self.embed, view=self)
        except discord.HTTPException as err:
            msg = "An embed needs content (title, description, or fields)."
            raise ValueError(msg) from err

    @discord.ui.button(
        label="Footer",
        style=discord.ButtonStyle.blurple,
        row=0,
    )
    async def set_footer(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        text, icon_url = await generate_modal(
            itx,
            "Set Footer",
            fields=[
                discord.ui.TextInput(
                    label="Footer Text",
                    placeholder="Up to 2048 characters",
                    required=False,
                    max_length=2048,
                    default=self.embed.footer.text,
                ),
                discord.ui.TextInput(
                    label="Icon URL",
                    placeholder="Must be HTTP[S] format",
                    required=False,
                    default=self.embed.footer.icon_url,
                ),
            ],
        )
        if text is None and icon_url is None:
            await self.embed.remove_footer()
        else:
            self.embed.set_footer(text=text, icon_url=icon_url)
        await itx.followup.edit_message(itx.message.id, embed=self.embed, view=self)

    @discord.ui.button(
        label="Images",
        style=discord.ButtonStyle.blurple,
        row=0,
    )
    async def set_image(self, itx: discord.Interaction, button: discord.Button) -> None:
        image, thumb = await generate_modal(
            itx,
            "Set Image / Thumbnail",
            fields=[
                discord.ui.TextInput(
                    label="Enter Image URL",
                    placeholder="Must be HTTP[S] format",
                    required=False,
                    default=self.embed.image.url if self.embed.image else None,
                ),
                discord.ui.TextInput(
                    label="Enter Thumbnail URL",
                    placeholder="Must be HTTP[S] format",
                    required=False,
                    default=self.embed.thumbnail.url if self.embed.thumbnail else None,
                ),
            ],
        )
        self.embed.set_image(url=image)
        self.embed.set_thumbnail(url=thumb)
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Fields:",
        style=discord.ButtonStyle.grey,
        disabled=True,
        row=1,
    )
    async def _header_fields(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        return

    @discord.ui.button(
        emoji="\N{HEAVY PLUS SIGN}",
        style=discord.ButtonStyle.success,
        row=1,
    )
    async def add_field(self, itx: discord.Interaction, button: discord.Button) -> None:
        name, value, inline, index = await generate_modal(
            itx,
            "Add Field",
            fields=[
                discord.ui.TextInput(
                    label="Field Name",
                    placeholder="Up to 256 characters",
                    required=False,
                    max_length=256,
                ),
                discord.ui.TextInput(
                    label="Field Value",
                    placeholder="Up to 1024 characters",
                    required=False,
                    style=discord.TextStyle.paragraph,
                    max_length=1024,
                ),
                discord.ui.TextInput(
                    label="Inline?",
                    required=False,
                    default="No",
                ),
                discord.ui.TextInput(
                    label="Index",
                    required=False,
                    placeholder="Where to insert the field, between 1 and 25. Default is 25 (at the end)",
                ),
            ],
        )
        if not index:
            index = "25"
        if not index.isdigit():
            msg = "Please enter a valid index (1-25)"
            raise ValueError(msg)
        index = int(index) - 1
        if index < 0 or index > 24:
            msg = "Please enter a valid index (1-25)"
            raise ValueError(msg)

        if name is None and value is None:
            msg = "Include a name or value to add a field."
            raise ValueError(msg)
        self.embed.insert_field_at(
            index,
            name=name,
            value=value,
            inline=inline.lower()
            in ("yes", "y", "true", "ok", "ye", "1", "on", "t", "yea", "sure", "yeah"),
        )
        self.remove_field.disabled = False
        self.edit_field.disabled = False
        self.add_field.disabled = len(self.embed.fields) >= 25
        await itx.followup.edit_message(itx.message.id, embed=self.embed, view=self)

    @discord.ui.button(
        emoji="\N{HEAVY MULTIPLICATION X}",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def remove_field(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        view = VanirView(self.ctx.bot, user=self.ctx.author)
        select = RemoveFieldDetachment(itx.message, self, self.embed)
        view.add_item(select)

        await itx.response.send_message(view=view, ephemeral=True)

    @discord.ui.button(
        emoji="\N{PENCIL}",
        style=discord.ButtonStyle.blurple,
        row=1,
    )
    async def edit_field(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        view = VanirView(self.ctx.bot, user=self.ctx.author)
        select = EditFieldDetachment(itx.message, self.embed)
        view.add_item(select)

        await itx.response.send_message(view=view, ephemeral=True)

    @discord.ui.button(
        label="JSON:",
        style=discord.ButtonStyle.grey,
        disabled=True,
        row=3,
    )
    async def _header_data(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        return

    @discord.ui.button(label="Export", style=discord.ButtonStyle.success, row=3)
    async def export(self, itx: discord.Interaction, button: discord.Button) -> None:
        file = discord.File(
            io.BytesIO(str(self.embed.to_dict()).encode()),
            filename="embed.json",
        )
        await itx.response.send_message(
            file=file,
            ephemeral=True,
        )

    @discord.ui.button(label="Import", style=discord.ButtonStyle.blurple, row=3)
    async def import_embed(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        values = await generate_modal(
            itx,
            "Import Embed",
            fields=[
                discord.ui.TextInput(
                    label="Enter JSON Embed Data",
                    style=discord.TextStyle.long,
                    default=str(self.embed.to_dict()),
                ),
            ],
        )
        try:
            self.embed = discord.Embed.from_dict(
                json.loads(values[0].replace("'", '"')),
            )
        except Exception as err:  # noqa: BLE001
            await itx.followup.send(
                embed=discord.Embed(
                    color=discord.Color.red(),
                    description=f"An error occurred while importing the embed: {err}",
                ),
                ephemeral=True,
            )
            return
        await itx.followup.edit_message(itx.message.id, embed=self.embed)

    @discord.ui.button(
        label="Send:",
        style=discord.ButtonStyle.grey,
        row=4,
        disabled=True,
    )
    async def _header_send(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        return

    @discord.ui.button(
        label="Preview",
        style=discord.ButtonStyle.blurple,
        row=4,
    )
    async def preview(self, itx: discord.Interaction, button: discord.Button) -> None:
        await itx.response.send_message(embed=self.embed, ephemeral=True)

    @discord.ui.button(
        label="Here",
        style=discord.ButtonStyle.success,
        row=4,
    )
    async def send(self, itx: discord.Interaction, button: discord.Button) -> None:
        if itx.message is not None:  # not ephemeral
            await itx.message.delete()
        await itx.response.defer()
        await itx.channel.send(embed=self.embed, view=None)

    @discord.ui.button(
        label="Other Channel",
        style=discord.ButtonStyle.blurple,
        row=4,
    )
    async def send_other(
        self,
        itx: discord.Interaction,
        button: discord.Button,
    ) -> None:
        values = await generate_modal(
            itx,
            "Send to Channel",
            fields=[discord.ui.TextInput(label="Enter Channel ID or Mention")],
        )
        channel = discord.utils.find(
            lambda c: values[0] in (str(c.id), c.mention, c.name),
            itx.guild.text_channels,
        )
        if channel is None:
            await itx.followup.send(
                embed=discord.Embed(
                    color=discord.Color.red(),
                    description="I couldn't find that channel. Make sure I can see it.",
                ),
                ephemeral=True,
            )
            return
        msg = await channel.send(embed=self.embed)
        await itx.followup.send(msg.jump_url, ephemeral=True)


class RemoveFieldDetachment(discord.ui.Select):
    def __init__(
        self,
        source_message: discord.Message,
        source_view: VanirView,
        embed: discord.Embed,
    ) -> None:
        self.source_message = source_message
        self.source_view = source_view
        self.embed = embed
        super().__init__(
            placeholder="Choose a field to remove",
            options=[
                discord.SelectOption(
                    label=f"{f.name[:60] + "..." if len(f.name) > 60 else f.name} (index {index + 1})",
                    description=f"{f.value[:96] + "..." if len(f.value) > 96 else f.value}",
                    value=index,
                )
                for index, f in enumerate(embed.fields)
            ],
            max_values=len(embed.fields),
        )

    async def callback(self, itx: discord.Interaction) -> None:
        indicies = map(int, self.values)
        for index in sorted(indicies, reverse=True):
            self.embed.remove_field(index)
        await itx.response.defer()
        await itx.delete_original_response()
        await self.source_message.edit(embed=self.embed, view=self.source_view)


class EditFieldDetachment(discord.ui.Select):
    # choose one field to edit
    # prompt modal EditFieldModal

    def __init__(self, source_message: discord.Message, embed: discord.Embed) -> None:
        self.source_message = source_message
        self.embed = embed
        super().__init__(
            placeholder="Choose a field to edit",
            options=[
                discord.SelectOption(
                    label=f"{f.name[:60] + "..." if len(f.name) > 60 else f.name} (index {index + 1})",
                    description=f"{f.value[:96] + "..." if len(f.value) > 96 else f.value}",
                    value=index,
                )
                for index, f in enumerate(embed.fields)
            ],
            max_values=1,
        )

    async def callback(self, itx: discord.Interaction) -> None:
        index = int(self.values[0])
        field = self.embed.fields[index]
        modal = EditFieldModal(self.source_message, self.embed, index, field)
        await itx.response.send_modal(modal)


class EditFieldModal(VanirModal, title="Edit Field"):
    def __init__(
        self,
        source_message: discord.Message,
        embed: discord.Embed,
        index: int,
        field: Any,
    ) -> None:
        self.source_message = source_message
        self.embed = embed
        self.index = index
        self.field = field
        self.name_input.default = field.name
        self.value_input.default = field.value
        self.inline_input.default = "Yes" if field.inline else "No"
        super().__init__(source_message.channel)

    name_input = discord.ui.TextInput(
        label="Field Name",
        placeholder="Up to 256 characters",
        required=False,
        max_length=256,
    )

    value_input = discord.ui.TextInput(
        label="Field Value",
        placeholder="Up to 1024 characters",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=1024,
    )

    inline_input = discord.ui.TextInput(
        label="Inline?",
        required=False,
        default="No",
    )

    async def on_submit(self, itx: discord.Interaction) -> None:
        name = self.name_input.value
        value = self.value_input.value
        inline = self.inline_input.value
        if not name and not value:
            msg = "Include a name or value to edit the field."
            raise ValueError(msg)
        self.embed.set_field_at(
            self.index,
            name=name,
            value=value,
            inline=inline.lower()
            in ("yes", "y", "true", "ok", "ye", "1", "on", "t", "yea", "sure", "yeah"),
        )
        await itx.response.defer()
        await itx.delete_original_response()
        await self.source_message.edit(embed=self.embed)


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Preview(bot))
