import asyncpg
from src import env
from discord.ext import commands


class StarBoardDB:
    def __init__(self):
        self.connection: asyncpg.connection.Connection

    @classmethod
    async def create(cls):

        cls.connection = await asyncpg.connect(**env.PSQL_CONNECTION)

    async def get_starboard_channel(self, guild_id: int):
        await self.connection.fetchrow(
            "SELECT channel_id FROM starboard WHERE guild_id = $1", guild_id
        )
