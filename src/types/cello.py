import wavelink
import discord


from src.util.format import format_children
from src.types.core import VanirContext


class VanirPlayer(wavelink.Player):
    initial_ctx: VanirContext
    dashboard: discord.Message | None = None
    filter_name: str | None = None

    async def embed(self, user: discord.User) -> discord.Embed:
        """Creates an embed for the current track."""
        if not self.playing:
            embed = VanirContext.syn_embed(
                title="No track playing...",
                user=user,
            )
        else:
            current = self.current
            title = current.title
            footer = f"By: {current.author}"
            embed = VanirContext.syn_embed(
                title=title,
                url=current.uri,
                user=self.initial_ctx.author,
            )
            embed.set_image(url=current.artwork)
            embed.set_footer(text=footer)

            embed.description = format_children(
                emoji=":information_source:",
                title="Info",
                children=[
                    (
                        "Duration",
                        f"{self.current.length // 60000}:{(self.current.length // 1000) % 60:02d}",
                    ),
                    (
                        "Album",
                        f"[{self.current.album.name}]({self.current.album.url})"
                        if self.current.album.name
                        else "<No Info>",
                    ),
                    ("Via Recommended?", "Yes" if self.current.recommended else "No"),
                ],
            )

        if not self.queue.is_empty:
            for i, track in enumerate(self.queue[:24], start=1):
                durs = f"{track.length // 60000}:{(track.length // 1000) % 60:02d}"
                embed.add_field(
                    name=f"`{i}.` {track.title}",
                    value=f"{track.author} | {durs}",
                    inline=False,
                )
            if len(self.queue) >= 25:
                embed.add_field(
                    name=f"*...and {len(self.queue) - 24} more*",
                    value=None,
                    inline=False,
                )
        else:
            embed.add_field(
                name="No tracks in queue",
                value="Use `+play <query or URL>` or the `Add Queue` button to add a track to the queue",
                inline=False,
            )

        return embed
