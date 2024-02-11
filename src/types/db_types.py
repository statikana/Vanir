import asyncpg
from discord import RawReactionActionEvent

from src import env
from discord.ext import commands


class StarBoard:
    def __init__(self):
        self.connection: asyncpg.connection.Connection = None

    @classmethod
    async def create(cls):

        cls.connection = await asyncpg.connect(**env.PSQL_CONNECTION)

    async def get_starboard_channel(self, guild_id: int):
        await self.connection.fetchval(
            "SELECT channel_id FROM starboard_data WHERE guild_id = $1",
            guild_id
        )

    async def add_star(self, guild_id: int, original_id: int, user_id: int) -> int:
        return await self.connection.fetchval(
            "INSERT INTO starboard_posts(starboard_post_id, guild_id, original_id, user_id) "
            "VALUES ($1, $2, $3, $4) "
            "ON CONFLICT DO UPDATE SET n_stars = n_stars+1 "
            "RETURNING n_stars",
            None, guild_id, original_id, user_id
        )

    async def get_starboard_post_id(self, original_id: int) -> int | None:
        return await self.connection.fetchval(
            "SELECT starboard_post_id FROM starboard_posts "
            "WHERE original_id = $1",
            original_id
        )

    async def set_starboard_post_id(self, starboard_post_id: int, guild_id: int, original_id: int, user_id: int, n_stars: int) -> None:
        await self.connection.execute(
            "INSERT INTO starboard_posts(starboard_post_id, guild_id, original_id, user_id, n_stars) "
            "VALUES ($1, $2, $3, $4, $5)",
            starboard_post_id, guild_id, original_id, user_id, n_stars
        )

    async def get_threshold(self, guild_id: int) -> int | None:
        return await self.connection.fetchval(
            "SELECT threshold FROM starboard_data WHERE guild_id = $1"
        )

    async def set_threshold(self, guild_id: int, threshold: int):
        return await self.connection.execute(
            "UPDATE starboard_data SET threshold = $2 WHERE guild_id = $1",
            guild_id, threshold
        )

