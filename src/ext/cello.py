import discord
from discord.ext import commands
import wavelink
from typing import cast

from src.types.core import Vanir, VanirContext
from src.types.command import VanirCog, vanir_command, VanirView, AcceptItx
from src.types.cello import VanirPlayer
from src.util.command import cog_hidden
from src.logging import book


class Cello(VanirCog):
    """getcho jams on"""

    emoji = "\N{VIOLIN}"

    @vanir_command(hidden=False)
    @commands.guild_only()
    async def debug(self, ctx: VanirContext):
        """Debug command to check the player state. Mostly for the devs"""
        player: VanirPlayer = cast(VanirPlayer, ctx.guild.voice_client)
        if player is None:
            return await ctx.send("No player.")

        content = []

        content.append(f"Current: {player.current.title if player.current else None}")

        content.append("Queue: ...")
        for track in player.queue:
            content.append(track.title)

        content.append(f"Autoplay: {player.autoplay}")
        content.append(f"Paused: {player.paused}")
        content.append(f"Queue size: {len(player.queue)}")
        content.append(f"Queue empty: {player.queue.is_empty}")
        content.append(f"Channel: {player.channel}")
        content.append(f"Initial context: {player.initial_ctx}")
        content.append("Queue history:")
        for track in player.queue.history:
            content.append(f"{track.title} {track.uri}")
        embed = VanirContext.syn_embed(title="Debug", description="\n".join(content), user=ctx.author)
        await ctx.send(embed=embed)

    @vanir_command()
    @commands.guild_only()
    async def play(
        self,
        ctx: VanirContext,
        file: discord.Attachment | None = commands.param(
            description="The file to play from. Can be None", default=None
        ),
        *,
        query: str | None = commands.param(
            description="What to play (YT/Spotify/Audio URL or search query)",
            default=None,
        ),
    ) -> None:
        """Plays a song from a query or file. If a file is provided, it will be used instead of a query."""

        if ctx.author.voice is None:
            return await ctx.send("You are not connected to a voice channel.")

        player: VanirPlayer = await ensure_player(ctx)

        if query is None:
            if file is None:
                return await ctx.send("No query or file provided.")
            query = file.url

        track = await evaluate_query(query)
        if track is None:
            return await ctx.send("No tracks found.")
        book.info(f"Obtained track '{track.title}' from query '{query}'")

        if player.playing:
            player.queue.put(track)
            book.info(f"\t...added to queue. Queue size: {len(player.queue)}")
        else:
            await player.play(track)
            book.info("\t...playing track.")

        embed = await player.embed(ctx.author)
        view = PlayerGUI(bot=ctx.bot, user=ctx.author, player=player)

        dsb = player.dashboard
        if dsb is not None:
            try:
                await dsb.edit(embed=embed, view=view)
            except discord.HTTPException:
                player.dashboard = await ctx.reply(embed=embed, view=view)
        else:
            player.dashboard = await ctx.reply(embed=embed, view=view)

    @vanir_command()
    @commands.guild_only()
    async def playing(self, ctx: VanirContext) -> None:
        """Re-send the queue dashboard"""
        player: VanirPlayer = cast(VanirPlayer, ctx.guild.voice_client)
        if player is None:
            return await ctx.send("Nothing is playing right now.")

        embed = await player.embed(ctx.author)
        view = PlayerGUI(bot=ctx.bot, user=ctx.author, player=player)

        try:
            await player.dashboard.delete()
        except discord.HTTPException:
            pass

        player.dashboard = await ctx.reply(embed=embed, view=view)


async def ensure_player(ctx: VanirContext) -> VanirPlayer:
    player: VanirPlayer = cast(VanirPlayer, ctx.guild.voice_client)
    if player is None:
        player = await ctx.author.voice.channel.connect(cls=VanirPlayer)
        player.autoplay = wavelink.AutoPlayMode.partial
        player.initial_ctx = ctx

    else:
        if player.channel != ctx.author.voice.channel:
            raise commands.BadArgument("You must be in the same channel as the bot.")

    return player


async def evaluate_query(query: str | None) -> wavelink.Playable | None:
    tracks = await wavelink.Playable.search(query, source="ytmsearch:")
    if not tracks:
        tracks = await wavelink.Playable.search(query)
        return tracks[0] if tracks else None

    if isinstance(track := tracks, wavelink.Playlist):
        return track.tracks[0]
    else:
        return tracks[0]


@cog_hidden
class Events(VanirCog):
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        book.info(f"Started {payload.track.title} in {payload.player.channel}")
        player: VanirPlayer = cast(VanirPlayer, payload.player)
        if player.dashboard is not None:
            embed = await player.embed(player.initial_ctx.author)
            view = PlayerGUI(
                bot=player.initial_ctx.bot,
                user=player.initial_ctx.author,
                player=player,
            )
            try:
                await player.dashboard.edit(embed=embed, view=view)
            except discord.HTTPException:
                pass

        if (
            payload.track.title not in (t.title for t in player.queue.history)
            and not player.queue.history.is_empty
        ):
            print("rec, adding")
            # recommended songs are not added to the queue history by default, add it here
            payload.player.queue.history.put(payload.track)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        book.info(f"Ended {payload.track.title} in {payload.player.channel}")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(
        self, payload: wavelink.TrackExceptionEventPayload
    ):
        error_msg = payload.exception["message"]
        book.error(
            f"Exception in {payload.track.title} in {payload.player.channel} | '{error_msg}'"
        )
        player: VanirPlayer = cast(VanirPlayer, payload.player)
        try:
            await player.initial_ctx.send(f"An error occurred: {error_msg}")
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        book.error(f"Stuck {payload.track.title} in {payload.player.channel}")


class PlayerGUI(VanirView):
    def __init__(
        self, bot: Vanir, *, user: discord.User | None = None, player: VanirPlayer
    ) -> None:
        super().__init__(bot=bot, user=user, accept_itx=AcceptItx.ANY)
        self.player = player
        self.select_classes: list[type[VanirSelect]] = [
            SkipToTrackSelect,
            FilterSelect,
            VolumeSelect,
        ]

        match player.paused:
            case True:
                self.pause.label = "Resume"
                self.pause.emoji = "\N{BLACK RIGHT-POINTING TRIANGLE}"
                self.pause.style = discord.ButtonStyle.success
            case False:
                self.pause.label = "Pause"
                self.pause.emoji = "\N{DOUBLE VERTICAL BAR}"
                self.pause.style = discord.ButtonStyle.primary

        match player.autoplay:
            case wavelink.AutoPlayMode.enabled:
                self.autoplay.label = "Autoplay: Full"
                self.autoplay.style = discord.ButtonStyle.success
            case wavelink.AutoPlayMode.partial:
                self.autoplay.label = "Autoplay: Continue"
                self.autoplay.style = discord.ButtonStyle.primary
            case wavelink.AutoPlayMode.disabled:
                self.autoplay.label = "Autoplay: Off"
                self.autoplay.style = discord.ButtonStyle.grey

        for sel in self.select_classes:
            instance = sel(player)
            instance.disabled = instance.should_disable()
            self.add_item(instance)

    @discord.ui.button(
        label="Restart",
        style=discord.ButtonStyle.secondary,
        emoji="\N{LEFTWARDS ARROW WITH HOOK}",
    )
    async def restart(self, itx: discord.Interaction, button: discord.ui.Button):
        await self.player.seek(0)
        await self.update_content(itx)

    @discord.ui.button(
        label="Pause",
        style=discord.ButtonStyle.primary,
        emoji="\N{DOUBLE VERTICAL BAR}",
    )
    async def pause(self, itx: discord.Interaction, button: discord.ui.Button):
        if self.player.paused:
            button.label = "Pause"
            button.emoji = "\N{DOUBLE VERTICAL BAR}"
            button.style = discord.ButtonStyle.primary
            await self.player.pause(False)
        else:
            button.label = "Resume"
            button.emoji = "\N{BLACK RIGHT-POINTING TRIANGLE}"
            button.style = discord.ButtonStyle.success
            await self.player.pause(True)

        await self.update_content(itx)

    @discord.ui.button(
        label="+15s",
        style=discord.ButtonStyle.primary,
        emoji="\N{CLOCKWISE DOWNWARDS AND UPWARDS OPEN CIRCLE ARROWS}",
    )
    async def seek_forward(self, itx: discord.Interaction, button: discord.ui.Button):
        current_position = self.player.position
        if current_position + 15000 > self.player.current.length:
            await self.player.skip()
        else:
            await self.player.seek(current_position + 15000)

        await self.update_content(itx)

    @discord.ui.button(
        label="Skip",
        style=discord.ButtonStyle.secondary,
        emoji="\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}",
    )
    async def skip(self, itx: discord.Interaction, button: discord.ui.Button):
        await self.player.skip()

        await self.update_content(itx)

    @discord.ui.button(
        label="Autoplay: Continue",
        style=discord.ButtonStyle.primary,
        emoji="\N{PERMANENT PAPER SIGN}",
    )
    async def autoplay(self, itx: discord.Interaction, button: discord.ui.Button):
        # off -> continue -> full
        # disabled -> partial -> enabled

        if self.player.autoplay == wavelink.AutoPlayMode.enabled:
            self.player.autoplay = wavelink.AutoPlayMode.disabled
            button.label = "Autoplay: Off"
            button.style = discord.ButtonStyle.grey
            description = "Music will not continue after a song ends."

        elif self.player.autoplay == wavelink.AutoPlayMode.disabled:
            self.player.autoplay = wavelink.AutoPlayMode.partial
            button.label = "Autoplay: Continue"
            button.style = discord.ButtonStyle.primary
            description = "Music will continue after a song ends."

        elif self.player.autoplay == wavelink.AutoPlayMode.partial:
            self.player.autoplay = wavelink.AutoPlayMode.enabled
            button.label = "Autoplay: Full"
            button.style = discord.ButtonStyle.success
            description = "Music will continue after a song ends and will search for similar songs."

        await self.update_content(itx)
        await itx.followup.send(description, ephemeral=True)

    @discord.ui.button(
        label="Add Queue",
        style=discord.ButtonStyle.success,
        emoji="\N{HEAVY PLUS SIGN}",
        row=1,
    )
    async def add_queue(self, itx: discord.Interaction, button: discord.ui.Button):
        modal = Enqueue(source_gui=self)
        await itx.response.send_modal(modal)

    @discord.ui.button(
        label="Clear Queue",
        style=discord.ButtonStyle.danger,
        emoji="\N{WASTEBASKET}",
        row=1,
    )
    async def clear_queue(self, itx: discord.Interaction, button: discord.ui.Button):
        if self.player.queue.is_empty:
            await itx.response.send_message("Queue is already empty!", ephemeral=True)
        else:
            self.player.queue.clear()
            await self.update_content(itx)

    @discord.ui.button(
        label="History",
        style=discord.ButtonStyle.secondary,
        emoji="\N{BOOKMARK}",
        row=1,
    )
    async def history(self, itx: discord.Interaction, button: discord.ui.Button):
        if self.player.queue.history.is_empty:
            await itx.response.send_message("No history stored", ephemeral=True)
            return

        embed = VanirContext.syn_embed(title="Queue History", user=itx.user)
        if self.player.queue.history is None or self.player.queue.history.is_empty:
            embed.description = "No history."
            await itx.response.send_message(embed=embed, ephemeral=True)
            return

        for track in self.player.queue.history[-24:]:
            embed.add_field(
                name=f"{track.title} | {track.length // 60000}:{(track.length // 1000) % 60:02d}",
                value=track.author,
                inline=False,
            )
        if len(self.player.queue.history) > 24:
            embed.set_footer(
                text=f"Showing 24 of {len(self.player.queue.history)} tracks."
            )

        await itx.response.send_message(embed=embed, ephemeral=True)

    async def update_content(self, itx: discord.Interaction):
        embed = await self.player.embed(itx.user)

        # remove all select options
        for item in self.children:
            if isinstance(item, VanirSelect):
                self.remove_item(item)

        for sel in self.select_classes:
            instance = sel(self.player)
            instance.disabled = instance.should_disable()
            self.add_item(instance)

        try:
            await itx.response.edit_message(embed=embed, view=self)
        except discord.InteractionResponded:
            await itx.message.edit(embed=embed, view=self)


class VanirSelect(discord.ui.Select):
    def should_disable(self, itx: discord.Interaction) -> bool:
        raise NotImplementedError


class SkipToTrackSelect(VanirSelect):
    def __init__(self, player: VanirPlayer) -> None:
        self.player = player
        options = [
            discord.SelectOption(
                label=f"{i+1}. {track.title}",
                description=f"{track.author} | {track.length}",
                value=i,
            )
            for i, track in enumerate(player.queue)
        ] or [discord.SelectOption(label="<no tracks available>", value="empty")]
        super().__init__(
            placeholder="Select a track to skip to",
            options=options,
            min_values=1,
            max_values=1,
            disabled=player.queue.is_empty,
            custom_id="skip_to_track",
        )

    async def callback(self, itx: discord.Interaction):
        if self.values[0] == "empty":
            await itx.response.defer()
            return

        index = int(self.values[0])

        for _ in range(index + 1):  # index 0 needs 1 skip, etc...
            await self.player.skip()

        await self.view.update_content(itx)  # type: ignore
        await itx.response.send_message("Skipped to track.", ephemeral=True)

    def should_disable(self) -> bool:
        return self.player.queue.is_empty


class FilterSelect(VanirSelect):
    def __init__(self, player: VanirPlayer) -> None:
        self.player = player
        values = [
            "<none>",
            "nightcore",
        ]
        options = [
            discord.SelectOption(
                label=value, value=value, default=value == player.filter_name
            )
            for value in values
        ]
        super().__init__(
            placeholder="Select a filter to apply",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="filter_select",
        )

    async def callback(self, itx: discord.Interaction):
        if self.values[0] == "<none>":
            await self.player.set_filters()
            self.player.filter_name = None
            await itx.response.send_message("Removed all filters.", ephemeral=True)
        else:
            await self.player.set_filters(PRESETS[self.values[0]])
            self.player.filter_name = self.values[0]
            await itx.response.send_message(
                f"Applied filter '{self.values[0]}'.", ephemeral=True
            )

        for option in self.options:
            option.default = option.value == self.values[0]

        await self.view.update_content(itx)  # type: ignore

    def should_disable(self) -> bool:
        return False


class VolumeSelect(VanirSelect):
    def __init__(self, player: VanirPlayer) -> None:
        self.player = player
        values = list(range(10, 210, 10))
        options = [
            discord.SelectOption(
                label=f"{vol}%{" [Default]" if vol == 100 else ""}",
                value=str(vol / 100.0),
                description="[May Cause Clipping]" if vol > 100 else None,
                default=vol == (player.filters.volume or 1) * 100,
            )
            for vol in values
        ]
        super().__init__(
            placeholder="Change volume...",
            options=options,
            max_values=1,
            min_values=1,
            custom_id="volume_select",
        )

    async def callback(self, itx: discord.Interaction) -> None:
        vol = float(self.values[0])
        existing = self.player.filters
        existing.volume = vol

        await self.player.set_filters(existing)

        for opt in self.options:
            opt.default = opt.value == vol

        await self.view.update_content(itx)
        await itx.followup.send(f"Set volume to {vol * 100}%", ephemeral=True)

    def should_disable(self) -> bool:
        return False


class Enqueue(discord.ui.Modal, title="Add a song to the queue"):
    def __init__(self, source_gui: PlayerGUI) -> None:
        super().__init__(title="Add a song to the queue")
        self.source_gui = source_gui

    query = discord.ui.TextInput(
        label="Query", placeholder="Search for a song", style=discord.TextStyle.short
    )

    async def on_submit(self, itx: discord.Interaction):
        track = await evaluate_query(self.query.value)
        player = self.source_gui.player
        if not player.playing and player.queue.is_empty:
            await player.play(track)
        else:
            player.queue.put(track)

        await self.source_gui.update_content(itx)


PRESETS = {
    "nightcore": wavelink.Filters.from_filters(
        timescale=wavelink.Timescale({}).set(pitch=1.2, speed=1.2, rate=1)
    ),
}


async def setup(bot: Vanir) -> None:
    await bot.add_cog(Cello(bot))
    await bot.add_cog(Events(bot))
