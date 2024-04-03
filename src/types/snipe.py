from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Generic, Iterator, TypeVar

if TYPE_CHECKING:
    from datetime import datetime

    import discord

StorageT = TypeVar("StorageT")
KeyT = TypeVar("KeyT")


class SnipeType(Enum):
    DELETED = "deleted"
    EDITED = "edited"


@dataclass
class SnipedMessage:
    message: discord.Message
    type: SnipeType
    sniped_at: datetime


class Stack(Generic[StorageT]):
    def __init__(self, size: int) -> None:
        """Initializes a new Stack object. The stack will only store the last `size` items."""
        self.size = size
        self.stack: list[StorageT] = []

    def push(self, item: StorageT) -> None:
        """Pushes an item on the top of the stack. If the stack is full, the oldest item will be removed."""
        if len(self.stack) >= self.size:
            self.stack.pop(0)
        self.stack.append(item)

    def pop(self) -> StorageT:
        """Pops the most recent item in the stack."""
        return self.stack.pop()

    def __len__(self) -> int:
        return len(self.stack)

    def __getitem__(self, index: int) -> StorageT:
        return self.stack[index]

    def __iter__(self) -> Iterator[StorageT]:
        return iter(self.stack)

    def __reversed__(self) -> list[StorageT]:
        return reversed(self.stack)


class Buckets(Generic[StorageT]):
    def __init__(
        self,
        size: int,
        *,
        per: Callable[[StorageT], KeyT],
        max_buckets: int | None = None,
    ) -> None:
        """
        Initializes a new Buckets object. The stack will only store the last `size` in each bucket defined by `per`.

        Args:
        ----
            size (int): The maximum number of items to store in each bucket.
            per (Callable[[StorageT], Any]): A function that takes an item and returns a key to determine the bucket.
                                             The number of unique keys this function can return is the maximum number of buckets.
            max_buckets (int | None): The maximum number of buckets to store. If None, all buckets will be stored.

        """
        self.size = size
        self.stacks: dict[KeyT, Stack[StorageT]] = {}
        self.per = per
        self.max_buckets = max_buckets

    def push(self, item: StorageT) -> None:
        """Pushes an item on the top of the stack. If the stack is full, the oldest item in the same bucket will be removed."""
        key = self.per(item)
        if key not in self.stacks:
            if self.max_buckets is not None and len(self.stacks) >= self.max_buckets:
                msg = "Maximum number of buckets reached."
                raise ValueError(msg)
            self.stacks[key] = Stack(self.size)
        self.stacks[key].push(item)

    def pop(self, snow: Any) -> StorageT:
        """Pops the most recent item in the stack in the same bucket as `snow`."""
        key = self.per(snow)
        return self.stacks[key].pop()

    @property
    def keytype(self) -> KeyT:
        return next(iter(self.stacks))

    def __len__(self) -> int:
        return sum(len(stack) for stack in self.stacks.values())

    def __getitem__(self, key: KeyT) -> Stack[StorageT]:
        return self.stacks[key]

    def __iter__(self) -> Iterator[StorageT]:
        for stack in self.stacks.values():
            yield from stack

    def __reversed__(self) -> list[StorageT]:
        return [item for stack in self.stacks.values() for item in reversed(stack)]

    def __contains__(self, key: KeyT) -> bool:
        return key in self.stacks

    def __delitem__(self, key: KeyT) -> None:
        del self.stacks[key]

    def __setitem__(self, key: KeyT, value: Stack[StorageT]) -> None:
        self.stacks[key] = value
