"""
Based upon Peter Norvig's spell checker
https://norvig.com/spell-correct.html.

Improved and expanded upon by me
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Generic, Iterator, TypeVar

from rapidfuzz.distance import Levenshtein

if TYPE_CHECKING:
    from collections import Counter


@dataclass
class Config:
    use_deletes: bool = True
    use_transposes: bool = True
    use_replaces: bool = True
    use_inserts: bool = True
    levenshtein_offset: int = 100


config = Config()


class FuzzyAC:
    def __init__(
        self,
        wordset: Counter[str],
        *,
        letterset: set[str] | None = None,
        config: Config = Config(),
    ) -> None:
        if letterset is None:
            letterset = {chr(i) for i in range(97, 123)}
        self.wordset = wordset
        self.letterset = letterset
        self.config = config

        self.words = set(wordset)

        self.N = sum(wordset.values())

    def proportion(self, word: str) -> float:
        return self.wordset[word] / self.N

    def _edits1(self, word: str) -> set[str]:
        _splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]

        candidates = set()
        if self.config.use_deletes:
            candidates.update({left + right[1:] for left, right in _splits if right})
        if self.config.use_transposes:
            candidates.update(
                {
                    left + right[1] + right[0] + right[2:]
                    for left, right in _splits
                    if len(right) > 1
                },
            )
        if self.config.use_replaces:
            candidates.update(
                {
                    left + c + right[1:]
                    for left, right in _splits
                    if right
                    for c in self.letterset
                },
            )
        if self.config.use_inserts:
            candidates.update(
                {left + c + right for left, right in _splits for c in self.letterset},
            )
        return candidates

    def edits(self, word: str, /, *, distance: int) -> set[str]:
        candidates = {word}
        for _ in range(distance):
            candidates = set.union(
                *[self._edits1(candidate) for candidate in candidates],
            )
        return candidates

    def candidates(self, word: str, /, *, distance: int) -> set[str]:
        return self.known(self.edits(word, distance=distance))

    def known(self, words: set[str]) -> set[str]:
        return set.intersection(words, self.wordset)

    def possible(self, word: str, /, *, distance: int, n: int) -> NHighestContianer:
        return n_highest(
            n, 
            self.candidates(word, distance=distance), 
            key=lambda trier: (self.config.levenshtein_offset-Levenshtein.distance(word, trier), self.proportion(trier))
        )

    def most_probable(self, word: str, /, *, distance: int = 1) -> str:
        return max(
            self.candidates(word, distance=distance), 
            key=lambda trier: (
                self.config.levenshtein_offset-Levenshtein.distance(word, trier), self.proportion(trier)
            )
        )



NHighestT = TypeVar("NHighestT")
NHighestValueT = TypeVar("NHighestValueT")


class NHighestContianer(Generic[NHighestT]):
    def __init__(self, n: int) -> None:
        self.stack: list[tuple[NHighestT, NHighestValueT]] = []
        self.n = n

    def attempt(self, item: NHighestT, value: NHighestValueT) -> None:
        if len(self) < self.n:
            self.stack.append((item, value))
            return
        
        smallest = min(self.stack, key=lambda t: t[1])
        if value > smallest[1]:
            self.stack.remove(smallest)
            self.stack.append((item, value))
        
    
    def get(self) -> list[tuple[NHighestT, NHighestValueT]]:
        return sorted(self.stack, key=lambda t: t[1])
            
    def __iter__(self) -> Iterator[tuple[NHighestT, NHighestValueT]]:
        return iter(self.stack)

    def __len__(self) -> int:
        return len(self.stack)
    
    def __getitem__(self, index: int) -> tuple[NHighestT, float]:
        return self.stack[index]


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def n_highest(
    n: int,
    data: set[NHighestT],
    *,
    key: Callable[[NHighestT], Any],
) -> NHighestContianer:
    stack = NHighestContianer(n)
    for item in data:
        stack.attempt(item, key(item))
    return stack
