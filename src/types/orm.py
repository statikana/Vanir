from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    import asyncpg


class DBBase:
    def __init__(self) -> None:
        self.pool: asyncpg.Pool | None = None

    def start(self, pool: asyncpg.Pool) -> None:
        self.pool = pool


class TASK(TypedDict):
    todo_id: int
    user_id: int
    title: str
    completed: bool
    timestamp_created: str


class TLINK(TypedDict):
    guild_id: int
    from_channel_id: int
    to_channel_id: int
    from_lang_code: str
    to_lang_code: str


class StatusRange(TypedDict):
    user_id: int
    start_time: datetime
    end_time: datetime
    status_type: str


class StatusTracker(TypedDict):
    user_id: int
    start_time: datetime
    status_type: str


class StarBoard(DBBase):
    async def get_config(self, guild_id: int) -> dict[str, int] | None:
        return await self.pool.fetchrow(
            "SELECT * FROM starboard_data WHERE guild_id = $1",
            guild_id,
        )

    async def set_config(self, guild_id: int, channel_id: int, threshold: int) -> None:
        await self.pool.execute(
            "INSERT INTO starboard_data(guild_id, channel_id, threshold) VALUES ($1, $2, $3) "
            "ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2, threshold = $3",
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

    async def set_post_id(self, original_id: int, starboard_post_id: int) -> None:
        await self.pool.execute(
            "UPDATE starboard_posts SET starboard_post_id = $2 WHERE original_id = $1",
            original_id,
            starboard_post_id,
        )

    async def remove_starboard_post(self, starboard_post_id: int) -> None:
        await self.pool.execute(
            "DELETE FROM starboard_posts WHERE starboard_post_id = $1",
            starboard_post_id,
        )

    async def set_star_threshold(self, guild_id: int, threshold: int) -> None:
        await self.pool.execute(
            "UPDATE starboard_data SET threshold = $2 WHERE guild_id = $1",
            guild_id,
            threshold,
        )

    async def remove_config(self, guild_id: int) -> None:
        await self.pool.execute(
            "DELETE FROM starboard_data WHERE guild_id = $1",
            guild_id,
        )

    async def get_post_data(self, original_id: int) -> int:
        return await self.pool.fetchrow(
            "SELECT * FROM starboard_posts WHERE original_id = $1",
            original_id,
        )

    async def set_starboard_post(
        self,
        original_id: int,
        starboard_post_id: int,
        guild_id: int,
        user_id: int,
        n_stars: int,
    ) -> None:
        await self.pool.execute(
            "INSERT INTO starboard_posts(original_id, starboard_post_id, guild_id, user_id, n_stars) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (original_id) DO UPDATE SET starboard_post_id = $2, n_stars = $5",
            original_id,
            starboard_post_id,
            guild_id,
            user_id,
            n_stars,
        )


class Currency(DBBase):
    def __init__(self, default_balance: int = 100) -> None:
        super().__init__()
        self.default_balance = default_balance

    async def balance(self, user_id: int) -> int:
        bal = await self.pool.fetchval(
            "SELECT balance FROM currency_data WHERE user_id = $1",
            user_id,
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

    async def add(self, user_id: int, amount: int) -> int:
        return await self.pool.fetchval(
            "UPDATE currency_data SET balance = currency_data.balance + $2 WHERE user_id = $1 RETURNING balance",
            user_id,
            amount,
        )


class Todo(DBBase):
    async def create(self, user_id: int, title: str) -> TASK:
        return await self.pool.fetchrow(
            "INSERT INTO todo_data(user_id, title) VALUES ($1, $2) RETURNING *",
            user_id,
            title,
        )

    async def get_by_user(self, user_id: int, *, include_completed: bool) -> list[TASK]:
        return await self.pool.fetch(
            "SELECT * FROM todo_data WHERE user_id = $1 AND completed = True OR $2",
            user_id,
            include_completed,
        )

    async def complete_by_id(self, *todo_ids: int) -> TASK | list[TASK] | None:
        vals = await self.pool.fetch(
            "UPDATE todo_data "
            "SET completed = True "
            "WHERE todo_id = ANY($1)"
            "RETURNING *",
            todo_ids,
        )
        if len(todo_ids) == 1:
            return vals[0]
        return vals

    async def uncomplete_by_id(self, *todo_ids: int) -> TASK | list[TASK] | None:
        vals = await self.pool.fetch(
            "UPDATE todo_data "
            "SET completed = False "
            "WHERE todo_id = ANY($1)"
            "RETURNING *",
            todo_ids,
        )
        if len(todo_ids) == 1:
            return vals[0]
        return vals

    async def complete_by_name(self, user_id: int, todo_title: str) -> TASK | None:
        return await self.pool.fetchrow(
            "UPDATE todo_data "
            "SET completed = True "
            "WHERE user_id = $1 AND title = $2 "
            "RETURNING *",
            user_id,
            todo_title,
        )

    async def get_by_id(self, todo_id: int) -> TASK | None:
        return await self.pool.fetchrow(
            "SELECT * FROM todo_data WHERE todo_id = $1",
            todo_id,
        )

    async def get_by_name(self, user_id: int, title: str) -> TASK | None:
        return await self.pool.fetchrow(
            "SELECT * FROM todo_data WHERE user_id = $1 AND title = $2",
            user_id,
            title,
        )

    async def remove(self, *todo_ids: int) -> list[TASK]:
        return await self.pool.fetch(
            "DELETE FROM todo_data WHERE todo_id = ANY($1) RETURNING *",
            todo_ids,
        )

    async def clear(self, user_id: int) -> list[TASK] | None:
        return await self.pool.fetch(
            "DELETE FROM todo_data WHERE user_id = $1 RETURNING *",
            user_id,
        )


class TLink(DBBase):
    async def create(
        self,
        guild_id: int,
        from_channel_id: int,
        to_channel_id: int,
        from_lang_code: str,
        to_lang_code: str,
    ) -> TLINK:
        return await self.pool.fetchrow(
            "INSERT INTO tlinks(guild_id, from_channel_id, to_channel_id, from_lang_code, to_lang_code) "
            "VALUES ($1, $2, $3, $4, $5) "
            "RETURNING *",
            guild_id,
            from_channel_id,
            to_channel_id,
            from_lang_code,
            to_lang_code,
        )

    async def get_guild_links(self, guild_id: int) -> list[TLINK]:
        return await self.pool.fetch(
            "SELECT * FROM tlinks WHERE guild_id = $1",
            guild_id,
        )

    async def remove(
        self,
        guild_id: int,
        from_channel_id: int,
        to_channel_id: int,
    ) -> TLINK | None:
        return await self.pool.fetchrow(
            "DELETE FROM tlinks "
            "WHERE guild_id = $1 AND from_channel_id = $2 AND to_channel_id = $3 "
            "RETURNING *",
            guild_id,
            from_channel_id,
            to_channel_id,
        )

    async def get_channel_links(self, channel_id: int) -> list[TLINK]:
        return await self.pool.fetch(
            "SELECT * FROM tlinks WHERE from_channel_id = $1 OR to_channel_id = $1",
            channel_id,
        )

    async def get_all_links(self) -> list[TLINK]:
        return await self.pool.fetch("SELECT * FROM tlinks")

    async def clear(self, guild_id: int) -> list[TLINK]:
        return await self.pool.fetch(
            "DELETE FROM tlinks WHERE guild_id = $1 RETURNING *",
            guild_id,
        )


"""
-- all completed status trackers
CREATE TABLE status_ranges (
    user_id BIGINT NOT NULL,
    status_type VARCHAR(8) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, start_time)
);

-- user changed their status, but it is not yet comfirmed how long this
-- status will last
-- waiting for another change to complete it, then will be moved to status_ranges
-- with the end_time set
CREATE TABLE status_trackers (
    user_id BIGINT NOT NULL,
    status_type VARCHAR(8) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, start_time)
);
"""


class Status(DBBase):
    async def get(
        self,
        user_id: int,
        after: datetime | None = None,
        include_partial: bool = True,
    ) -> list[StatusRange]:
        if after is None:
            after = datetime.min

        after = after.replace(tzinfo=None)
        confirmed = await self.pool.fetch(
            "SELECT * FROM status_ranges WHERE user_id = $1 AND start_time >= $2",
            user_id,
            after,
        )

        if include_partial:
            partial = await self.pool.fetch(
                "SELECT * FROM status_trackers WHERE user_id = $1 AND start_time >= $2",
                user_id,
                after,
            )
            partial = [
                {**entry, "end_time": datetime.now(tz=None)} for entry in partial
            ]
            return confirmed + partial

        return confirmed

    async def status_update(
        self,
        user_id: int,
        status_type: str,
    ) -> StatusTracker:
        # first, find any outstanding status trackers
        # and update them to the current time
        # then move to status_ranges
        # there should only be one outstanding status tracker
        current = await self.pool.fetchrow(
            "DELETE FROM status_trackers WHERE user_id = $1 RETURNING *",
            user_id,
        )
        if current is not None:
            current = {**current, "end_time": datetime.now(tz=None)}
            await self.pool.execute(
                "INSERT INTO status_ranges(user_id, status_type, start_time, end_time) "
                "VALUES ($1, $2, $3, $4)",
                current["user_id"],
                current["status_type"],
                current["start_time"],
                current["end_time"],
            )

        # create a new status tracker
        return await self.pool.fetchrow(
            "INSERT INTO status_trackers(user_id, status_type, start_time) "
            "VALUES ($1, $2, $3)"
            "RETURNING *",
            user_id,
            status_type,
            datetime.now(tz=None),
        )
