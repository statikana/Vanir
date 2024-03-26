from dataclasses import dataclass

import aiohttp

from config import piston_api_url


@dataclass
class PistonRuntime:
    language: str
    version: str
    aliases: list[str]
    runtime: str | None = None


@dataclass
class PistonExecutable:
    name: str
    content: str
    encoding: str = "utf8"


@dataclass
class PistonExecutionResult:
    stdout: str
    stderr: str
    output: str
    code: int
    signal: int | None


@dataclass
class PistonExecutionResponse:
    language: str
    version: str
    run: PistonExecutionResult


@dataclass
class PistonPackage:
    language: str
    language_version: str
    installed: bool = False


class PistonORM:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def check_running(self) -> bool:
        """Check if the piston api is running."""
        try:
            response = await self.session.get(piston_api_url + "/check")
            response.raise_for_status()
            return True
        except aiohttp.ClientResponseError:
            return False

    async def runtimes(self) -> list[PistonRuntime]:
        """Get all available runtimes that are currently installed"""
        response = await self.session.get(piston_api_url + "/runtimes")
        response.raise_for_status()
        json = await response.json()
        print(json)
        return [PistonRuntime(**runtime) for runtime in json]

    async def execute(
        self,
        *,
        package: PistonPackage,
        files: list[PistonExecutable],
        stdin: str = "",
        args: list[str] = [],
        compile_timeout: int = 10000,
        run_timeout: int = 3000,
        compile_memory_limit: int = 200000000,  # 200MB
        run_memory_limit: int = 200000000,  # 200MB
    ) -> PistonExecutionResponse:
        """Execute code via a"""
        json = {
            "language": package.language,
            "version": package.language_version,
            "files": [
                {"name": file.name, "content": file.content, "encoding": file.encoding}
                for file in files
            ],
            "stdin": stdin,
            "args": args,
            "compile_timeout": compile_timeout,
            "run_timeout": run_timeout,
            "compile_memory_limit": compile_memory_limit,
            "run_memory_limit": run_memory_limit,
        }
        response = await self.session.post(piston_api_url + "/execute", json=json)
        response.raise_for_status()

        json = await response.json()
        return PistonExecutionResponse(
            language=json["language"],
            version=json["version"],
            run=PistonExecutionResult(**json["run"]),
        )

    async def packages(self) -> list[PistonPackage]:
        """Get all available packages"""
        response = await self.session.get(piston_api_url + "/packages")
        response.raise_for_status()
        json = await response.json()
        print(json)
        return [PistonPackage(**package) for package in json]

    async def install_package(self, package: PistonPackage) -> PistonPackage:
        response = await self.session.post(
            piston_api_url + "/packages",
            json={"language": package.language, "version": package.language_version},
            timeout=aiohttp.ClientTimeout(total=60 * 10),
        )
        response.raise_for_status()
        json = await response.json()
        print(json)
        return PistonPackage(
            language=json["language"], language_version=json["version"], installed=True
        )

    async def uninstall_package(self, package: PistonPackage) -> PistonPackage:
        response = await self.session.delete(
            piston_api_url + "/packages",
            json={"language": package.language, "version": package.language_version},
        )
        response.raise_for_status()
        json = await response.json()
        return PistonPackage(**json, installed=False)
