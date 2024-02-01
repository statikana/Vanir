import asyncio

from src.types.charm_types import Charm
from src.env import DISCORD_TOKEN


async def main():
    charm = Charm()
    await charm.start(token=DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
