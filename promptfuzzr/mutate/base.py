from __future__ import annotations

from typing import Protocol


class Mutator(Protocol):
    name: str

    def mutate(self, seed_text: str, count: int = 10) -> list[str]:
        ...
