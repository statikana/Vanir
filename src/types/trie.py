from __future__ import annotations

from typing import Generator, Iterator

import rapidfuzz


def shingle(s: str, n: int) -> list[str]:
    """Generates N-grams from a given string."""
    return {s[i : i + n] for i in range(len(s) - n + 1)}


class TrieNode:
    """Represents a node in the Trie data structure."""

    def __init__(self) -> None:
        self.children: dict[
            str,
            TrieNode,
        ] = {}  # Dictionary to store child nodes (letters)
        self.is_word = False  # Flag to indicate if this node represents a complete word
        self.shingles = set()  # Set to store N-grams of the word

    def __iter__(self) -> Iterator[tuple[str, TrieNode]]:
        yield from self.children.items()


class Trie:
    """Implements the Trie data structure for efficient word storage and retrieval."""

    def __init__(self) -> None:
        self.root = TrieNode()  # Root node of the Trie

    def __iter__(self) -> Generator[tuple[str, TrieNode], None, None]:
        stack = [self.root]
        while stack:
            current = stack.pop()
            for char, node in current:
                stack.append(node)
                yield char, node

    def insert(self, word: str) -> None:
        """Inserts a word into the Trie."""
        current = self.root
        for char in word:
            if char not in current.children:
                current.children[char] = TrieNode()
            current = current.children[char]
        current.is_word = True  # Mark the end of the word
        current.shingles = shingle(word, 2)  # Store N-grams of the word

    def find(self, chars: str) -> TrieNode:
        """Searches for a word in the Trie and returns the node if found."""
        current = self.root
        for char in chars:
            if char not in current.children:
                return False
            current = current.children[char]
        return current

    def exists(self, word: str) -> bool:
        """Checks if a given word exists in the Trie."""
        node = self.find(word)
        return node is not None and node.is_word

    def prefix(self, prefix: str) -> bool:
        """Checks if a given prefix exists in the Trie."""
        current = self.root
        for char in prefix:
            if char not in current.children:
                return False
            current = current.children[char]
        return True  # Prefix found, regardless of whether it's a complete word

    def delete(self, word: str) -> None:
        """Deletes a word from the Trie."""

        def _delete(node: TrieNode, word: str, index: int):
            if index == len(word):
                if not node.is_word:
                    return False
                node.is_word = False
                return len(node.children) == 0

            char = word[index]
            if char not in node.children:
                return False

            child = node.children[char]
            delete_child = _delete(child, word, index + 1)

            if delete_child:
                del node.children[char]
                return len(node.children) == 0

            return False

        _delete(self.root, word, 0)

    def iter_words(self) -> Generator[tuple[str, TrieNode], None, None]:
        stack = [("", self.root)]
        while stack:
            prefix, current = stack.pop()
            if current.is_word:
                yield prefix, current
            for char, node in current:
                stack.append((prefix + char, node))

    def autocorrect_ngram(self, source: str, k: int = 2) -> list[str]:
        source_shingles = shingle(source, k)

        n_shingles = len(source_shingles)
        min_mutual_tokens = n_shingles - 1
        max_length_diff = 2

        candidates = set()

        for word, node in self.iter_words():  # Iterate over all words in the Trie
            ix = set.intersection(node.shingles, source_shingles)
            lendiff = abs(len(node.shingles) - n_shingles)
            if len(ix) >= min_mutual_tokens and lendiff <= max_length_diff:
                candidates.add(word)

        # Sort the candidates based on their similarity to the source word
        # len(candidates) <= ~10-20 usually, so Levenshtein distance isn't really impactful
        return sorted(
            candidates,
            key=lambda s: rapidfuzz.distance.DamerauLevenshtein.distance(s, source),
            reverse=True,
        )
