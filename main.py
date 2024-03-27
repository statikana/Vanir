import asyncio

from logging_setup import logging_setup
from src.env import DISCORD_TOKEN
from src.types.core import Vanir


async def main() -> None:
    bot = Vanir()
    await bot.start(token=DISCORD_TOKEN)


if __name__ == "__main__":
    logging_setup()
    asyncio.run(main())
