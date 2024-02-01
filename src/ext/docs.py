import discord
from discord import app_commands
from src.types.command_types import CharmCog


class Docs(CharmCog):
    @app_commands.command()
    async def docs(self, itx: discord.Interaction, project: str, query: str | None = None):
        pass
