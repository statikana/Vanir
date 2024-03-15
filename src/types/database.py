import asyncpg


class DBBase:
    def __init__(self):
        self.pool: asyncpg.connection.Connection = None  # type: ignore

    def start(self, pool: asyncpg.Pool) -> None:

        self.pool = pool


class StarBoard(DBBase):

    async def get_starboard_channel(self, guild_id: int):
        return await self.pool.fetchval(
            "SELECT channel_id FROM starboard_data WHERE guild_id = $1", guild_id
        )

    async def set_starboard_channel(
        self, guild_id: int, channel_id: int, threshold: int
    ):
        await self.pool.execute(
            "INSERT INTO starboard_data(guild_id, channel_id, threshold) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id) DO UPDATE SET channel_id=$2, threshold=$3",
            guild_id,
            channel_id,
            threshold,
        )

    async def add_star(self, guild_id: int, original_id: int, user_id: int) -> int:
        return await self.pool.fetchval(
            "INSERT INTO starboard_posts(starboard_post_id, guild_id, original_id, user_id, n_stars) "
            "VALUES ($1, $2, $3, $4, 1) "
            "ON CONFLICT (original_id) DO UPDATE SET n_stars = starboard_posts.n_stars+1 "
            "RETURNING n_stars",
            None,
            guild_id,
            original_id,
            user_id,
        )

    async def remove_star(self, guild_id: int, original_id: int, user_id: int) -> int:
        return await self.pool.fetchval(
            "INSERT INTO starboard_posts(starboard_post_id, guild_id, original_id, user_id, n_stars) "
            "VALUES ($1, $2, $3, $4, 0) "
            "ON CONFLICT (original_id) DO UPDATE SET n_stars = starboard_posts.n_stars-1 "
            "RETURNING n_stars",
            None,
            guild_id,
            original_id,
            user_id,
        )

    async def get_starboard_post_id(self, original_id: int) -> int | None:
        return await self.pool.fetchval(
            "SELECT starboard_post_id FROM starboard_posts WHERE original_id = $1",
            original_id,
        )

    async def set_starboard_post_id(
        self,
        starboard_post_id: int,
        guild_id: int,
        original_id: int,
        user_id: int,
        n_stars: int,
    ) -> None:
        await self.pool.execute(
            "INSERT INTO starboard_posts(starboard_post_id, guild_id, original_id, user_id, n_stars) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (original_id) DO UPDATE SET starboard_post_id = $1, n_stars = $5",
            starboard_post_id,
            guild_id,
            original_id,
            user_id,
            n_stars,
        )

    async def remove_starboard_post(self, starboard_post_id: int):
        await self.pool.execute(
            "DELETE FROM starboard_posts WHERE starboard_post_id = $1",
            starboard_post_id,
        )

    async def get_threshold(self, guild_id: int) -> int | None:
        return await self.pool.fetchval(
            "SELECT threshold FROM starboard_data WHERE guild_id = $1", guild_id
        )

    async def set_threshold(self, guild_id: int, threshold: int):
        return await self.pool.execute(
            "UPDATE starboard_data SET threshold = $2 WHERE guild_id = $1",
            guild_id,
            threshold,
        )

    async def remove_data(self, guild_id: int) -> None:
        await self.pool.execute(
            "DELETE FROM starboard_data WHERE guild_id = $1", guild_id
        )


class Currency(DBBase):
    def __init__(self, default_balance: int = 100) -> None:
        super().__init__()
        self.default_balance = default_balance

    async def balance(self, user_id: int) -> int:
        bal = await self.pool.fetchval(
            "SELECT balance FROM currency_data WHERE user_id = $1", user_id
        )
        if bal is None:
            await self.pool.execute(
                "INSERT INTO currency_data (user_id, balance) VALUES ($1, $2)",
                user_id,
                self.default_balance,
            )
            return self.default_balance
        return bal

    async def transfer(self, from_id: int, to_id: int, amount: int) -> tuple[int, int]:
        new_from_bal = await self.pool.fetchval(
            "UPDATE currency_data SET "
            "balance = currency_data.balance - $2 "
            "WHERE user_id = $1 "
            "RETURNING balance",
            from_id,
            amount,
        )
        new_to_bal = await self.pool.fetchval(
            "UPDATE currency_data SET "
            "balance = currency_data.balance + $2 "
            "WHERE user_id = $1 "
            "RETURNING balance",
            to_id,
            amount,
        )
        return new_from_bal, new_to_bal

    async def set_balance(self, user_id: int, amount: int) -> None:
        await self.pool.execute(
            "UPDATE currency_data SET balance = $2 WHERE user_id = $1",
            user_id,
            amount,
        )


class Todo(DBBase):
    async def create_todo(self, user_id: int, title: str):
        return await self.pool.fetchrow(
            "INSERT INTO todo_data(user_id, title) VALUES ($1, $2) RETURNING *",
            user_id,
            title,
        )

    async def get_todos_by_user(self, user_id: int, include_completed: bool):
        return await self.pool.fetch(
            "SELECT * FROM todo_data WHERE user_id = $1 AND completed = True OR $2",
            user_id,
            include_completed,
        )

    async def complete_todo_by_id(self, user_id: int, todo_id: int):
        try:
            todo_id = int(todo_id)
        except TypeError:
            return None
        return await self.pool.fetchrow(
            "UPDATE todo_data "
            "SET completed = True "
            "WHERE user_id = $1 AND todo_id = $2 "
            "RETURNING *",
            user_id,
            todo_id,
        )

    async def complete_todo_by_name(self, user_id: int, todo_title: str):
        return await self.pool.fetchrow(
            "UPDATE todo_data "
            "SET completed = True "
            "WHERE user_id = $1 AND title = $2 "
            "RETURNING *",
            user_id,
            todo_title,
        )

    async def get_todo_by_id(self, user_id: int, todo_id: int):
        return await self.pool.fetchrow(
            "SELECT * FROM todo_data WHERE user_id = $1 AND todo_id = $2",
            user_id,
            todo_id,
        )

    async def get_task_id_by_name(self, user_id: int, title: str):
        return await self.pool.fetchval(
            "SELECT todo_id FROM todo_data WHERE user_id = $1 AND title = $2",
            user_id,
            title,
        )

    async def remove_todo(self, user_id: int, todo_id: int):
        return await self.pool.fetchrow(
            "DELETE FROM todo_data "
            "WHERE user_id = $1 AND todo_id = $2 "
            "RETURNING *",
            user_id,
            todo_id,
        )

    async def clear(self, user_id: int):
        return await self.pool.fetch(
            "DELETE FROM todo_data WHERE user_id = $1 RETURNING *", user_id
        )


class LiveTranslationLinks(DBBase):
    async def create_link(
        self, guild_id: int, from_channel_id: int, to_channel_id: int
    ):
        return await self.pool.fetch(
            "INSERT INTO live_translation_links(guild_id, from_channel_id, to_channel_id) "
            "VALUES ($1, $2, $3) "
            "RETURNING *",
            guild_id,
            from_channel_id,
            to_channel_id,
        )

    async def get_guild_links(self, guild_id: int):
        return await self.pool.fetch(
            "SELECT * FROM live_translation_links WHERE guild_id = $1",
            guild_id,
        )

    async def remove_link(
        self, guild_id: int, from_channel_id: int, to_channel_id: int
    ):
        return await self.pool.fetch(
            "DELETE FROM live_translation_links "
            "WHERE guild_id = $1 AND from_channel_id = $2 AND to_channel_id = $3 "
            "RETURNING *",
            guild_id,
            from_channel_id,
            to_channel_id,
        )

    async def get_channel_links(self, channel_id: int):
        return await self.pool.fetch(
            "SELECT * FROM live_translation_links "
            "WHERE from_channel_id = $1 OR to_channel_id = $1",
            channel_id,
        )

    async def clear(self, guild_id: int):
        return await self.pool.fetch(
            "DELETE FROM live_translation_links WHERE guild_id = $1 RETURNING *",
            guild_id,
        )
