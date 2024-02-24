import asyncpg


class DBBase:
    def __init__(self):
        self.con: asyncpg.connection.Connection = None  # type: ignore

    def start(self, connection: asyncpg.connection.Connection) -> None:

        self.con = connection


class StarBoard(DBBase):

    async def get_starboard_channel(self, guild_id: int):
        return await self.con.fetchval(
            "SELECT channel_id FROM starboard_data WHERE guild_id = $1", guild_id
        )

    async def set_starboard_channel(
        self, guild_id: int, channel_id: int, threshold: int
    ):
        await self.con.execute(
            "INSERT INTO starboard_data(guild_id, channel_id, threshold) "
            "VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id) DO UPDATE SET channel_id=$2, threshold=$3",
            guild_id,
            channel_id,
            threshold,
        )

    async def add_star(self, guild_id: int, original_id: int, user_id: int) -> int:
        return await self.con.fetchval(
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
        return await self.con.fetchval(
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
        return await self.con.fetchval(
            "SELECT starboard_post_id FROM starboard_posts " "WHERE original_id = $1",
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
        await self.con.execute(
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
        await self.con.execute(
            "DELETE FROM starboard_posts WHERE " "starboard_post_id = $1",
            starboard_post_id,
        )

    async def get_threshold(self, guild_id: int) -> int | None:
        return await self.con.fetchval(
            "SELECT threshold FROM starboard_data WHERE guild_id = $1", guild_id
        )

    async def set_threshold(self, guild_id: int, threshold: int):
        return await self.con.execute(
            "UPDATE starboard_data SET threshold = $2 WHERE guild_id = $1",
            guild_id,
            threshold,
        )

    async def remove_data(self, guild_id: int) -> None:
        await self.con.execute(
            "DELETE FROM starboard_data WHERE guild_id = $1", guild_id
        )


class Currency(DBBase):
    def __init__(self, default_balance: int = 100) -> None:
        super().__init__()
        self.default_balance = default_balance

    async def balance(self, user_id: int) -> int:
        bal = await self.con.fetchval(
            "SELECT balance FROM currency_data WHERE " "user_id = $1", user_id
        )
        if bal is None:
            await self.con.execute(
                "INSERT INTO currency_data (user_id, balance) " "VALUES ($1, $2)",
                user_id,
                self.default_balance,
            )
            return self.default_balance
        return bal

    async def transfer(self, from_id: int, to_id: int, amount: int) -> tuple[int, int]:
        new_from_bal = await self.con.fetchval(
            "UPDATE currency_data SET "
            "balance = currency_data.balance - $2 "
            "WHERE user_id = $1 "
            "RETURNING balance",
            from_id,
            amount,
        )
        new_to_bal = await self.con.fetchval(
            "UPDATE currency_data SET "
            "balance = currency_data.balance + $2 "
            "WHERE user_id = $1 "
            "RETURNING balance",
            to_id,
            amount,
        )
        return new_from_bal, new_to_bal

    async def set_balance(self, user_id: int, amount: int) -> None:
        await self.con.execute(
            "UPDATE currency_data SET " "balance = $2 " "WHERE user_id = $1",
            user_id,
            amount,
        )
