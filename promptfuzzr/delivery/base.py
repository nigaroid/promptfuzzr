from __future__ import annotations

from typing import Protocol


class DeliveryChannel(Protocol):
    name: str

    def deliver(self, payload: str, **kwargs) -> str:
        ...

    def cleanup(self, reference: str) -> None:
        ...
