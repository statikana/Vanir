import asyncio

from src.types.core import Vanir
from src.env import DISCORD_TOKEN
from logging_setup import logging_setup


async def main():
    bot = Vanir()
    await bot.start(token=DISCORD_TOKEN)


if __name__ == "__main__":
    logging_setup()
    asyncio.run(main())
