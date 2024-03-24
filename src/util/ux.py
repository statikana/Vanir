import discord


class BasicInput(discord.ui.Modal):
    def __init__(self, title: str):
        super().__init__(title=title, timeout=None)

    async def on_submit(self, itx: discord.Interaction, /) -> None:
        await itx.response.defer()


async def generate_modal(
    itx: discord.Interaction, title: str, *, fields: list[discord.TextInput]
) -> list[str]:
    modal = BasicInput(title=title)

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
