import asyncio
import logging

from logging_setup import logging_setup
from src.env import DISCORD_TOKEN
from src.types.core import Vanir


async def main():
    bot = Vanir()
    await bot.start(token=DISCORD_TOKEN)


if __name__ == "__main__":
    logging_setup()
    logging.info("Starting")
    asyncio.run(main())
