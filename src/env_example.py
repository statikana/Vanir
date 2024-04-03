# To run, create a file in src/ titled env.py and replace any
# ellipses with the appropriate values. If you don't include
# all of the values, the bot will probably break upon startup.

# Needed for: Basic operation
# If not included, breaks upon: Startup
from __future__ import annotations

DISCORD_TOKEN: str = ...

# Needed for: Connection to the PostgreSQL database
# If not included, breaks upon: Startup
PSQL_CONNECTION: dict[str, str | int] = {
    "host": ...,
    "port": ...,
    "database": ...,
    "user": ...,
    "password": ...,
}

# Needed for: Translation cog
# If not included, breaks upon: Translation command
DEEPL_API_KEY: str = ...

# Needed for: Waifu cog
# If not included, breaks upon: Waifu commands
WAIFU_IM_API_TOKEN: str = ...
