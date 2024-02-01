from discord.ext import commands

from src import util
from src.types.charm_types import Charm, CharmContext
from src.types.command_types import CharmCog

docs = commands.HybridGroup(name="docs")


class Docs(CharmCog):
    @docs.command(name="project")
    async def project(
            self,
            ctx: CharmContext,
            slug: str
    ) -> None:
        """
        Shows information about a certain project on `readthedocs.org`.
        :param ctx:
        :param slug: The 'slug' name of the project - no spaces or special characters. Will get formatted internally, too.
        """
        slug = util.ensure_slug(slug)

        response = await self.charm.session.docs_get(f"/projects/{slug}")
        if not response.ok:
            raise ValueError(f"Could not get project: Code {response.status} from readthedocs.org API")

        data = await response.json()

        embed = ctx.embed(
            title=f"Project `{data['name']}` (`{data['slug']}, id `{data['id']})",
            url=data["repository"]["url"]
        )

        shown_data = {
            "Created": data["created"],
            "Modified": data["modified"],
            "Language": data["language"]["name"],
            "Default Control": f"{data['default_branch']}@{data['default_version']}",
            "Tags": ", ".join(data["tags"][:7]),
            "Owners": ", ".join(user["username"] for user in data["users"]),
            "Urls": " - ".join([f"[{name}]({url})" for name, url in data["urls"]]),
            "Privacy": data["privacy_level"],
        }
        embed.description = util.format_dict(shown_data)

        await ctx.send(embed=embed)


async def setup(bot: Charm):
    await bot.add_cog(Docs(bot))
