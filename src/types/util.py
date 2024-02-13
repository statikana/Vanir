from dataclasses import dataclass

import discord


@dataclass
class MessageState:
    content: str
    embeds: list[discord.Embed]
    view: discord.ui.View

    @classmethod
    def from_message(cls, message: discord.Message):
        return MessageState(
            content=message.content,
            embeds=message.embeds,
            view=discord.ui.View.from_message(message),
        )


class MessageStateCache:
    def __init__(self):
        self.states: list[MessageState] = []
        self.index: int = 0
        self.last_loaded_index: int | None = None

    def cache(self, state: MessageState):
        self.states.append(state)
        # print("CACHEING")

        # increment index unless it would cause an index error
        self.index = min(len(self.states) - 1, self.index + 1)

    async def load(self, onto: discord.PartialMessage, index: int = None):
        if index is None:
            index = self.index
        index = max(index, 0)
        # print(index, ":load")
        # print(self.states)

        state = self.states[index]

        update_movement_buttons(
            state.view, index, self.last_loaded_index, len(self.states)
        )

        await onto.edit(
            content=state.content, embeds=state.embeds, view=copy_view(state.view)
        )
        self.last_loaded_index = index

    def forking_movement(self):
        # using self.last_loaded_index, cut off anything ahead
        if self.last_loaded_index is not None:
            self.states = self.states[: self.last_loaded_index + 1]


def find_movement_buttons(view: discord.ui.View):
    # This is a kind of silly way to find the movement buttons on the view but it works
    left: discord.ui.Button | None = discord.utils.find(
        lambda c: (
            (c.emoji.name == "\N{Black Left-Pointing Triangle}")
            if hasattr(c, "emoji")
            else False
        ),
        view.children,
    )
    right: discord.ui.Button | None = discord.utils.find(
        lambda c: (
            (c.emoji.name == "\N{Black Right-Pointing Triangle}")
            if hasattr(c, "emoji")
            else False
        ),
        view.children,
    )
    return left, right


def update_movement_buttons(
    view: discord.ui.View, index: int, last_loaded_index: int | None, n_states: int
) -> None:
    """
    Determines which movement buttons (left, right) should be active, given the index and last loaded index of the message state cache,
    and the number of states being held
    """
    # print("update_movement_buttons")
    left, right = find_movement_buttons(view)
    # print(left, right)

    left.disabled = (
        n_states == 0 or last_loaded_index is None or last_loaded_index == index
    )

    # TODO: fix this
    right.disabled = index >= n_states - 1


def copy_view(view: discord.ui.View) -> discord.ui.View:
    new = discord.ui.View(timeout=view.timeout)

    for c in view.children:
        new.add_item(c)

    return new


def update_as_forking_movement(view: discord.ui.View):
    left, right = find_movement_buttons(view)
    # print(left, right, view.children)
    left.disabled = False
    right.disabled = True
