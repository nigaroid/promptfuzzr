"""Common interface every mutator implements.

A mutator takes a seed payload string and yields N variants. Keep
mutators pure (no network calls, no target awareness) so they can be
unit tested in isolation and composed into mutation_chains.
"""

from __future__ import annotations

from typing import Protocol


class Mutator(Protocol):
    name: str

    def mutate(self, seed_text: str, count: int = 10) -> list[str]:
        """Return up to `count` mutated variants of seed_text."""
        ...
