import aiohttp

from src.env import READ_THE_DOCS_API_KEY


class VanirSession(aiohttp.ClientSession):
    def __init__(self):
        super().__init__(
            raise_for_status=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0"
            }
        )

    async def docs_get(self, path: str, headers: dict[str, str] = None, **kwargs) -> aiohttp.ClientResponse:
        """Prepends the base API URL (https://readthedocs.org/api/v3) of readthedocs to the request, and adds the key header"""
        if headers is None:
            headers = {}
        headers["Authorization"] = f"token {READ_THE_DOCS_API_KEY}"
        return await super().get("https://readthedocs.org/api/v3" + path, headers=headers, **kwargs)
