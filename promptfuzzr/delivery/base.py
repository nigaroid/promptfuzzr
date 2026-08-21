"""Common interface every delivery channel implements.

A channel takes a mutated payload and "places" it wherever that
surface requires (a served HTML page, a sent email, a written file, a
RAG-store document, a tool registry entry), then returns a reference
the orchestrator uses to point the target at it.
"""

from __future__ import annotations

from typing import Protocol


class DeliveryChannel(Protocol):
    name: str

    def deliver(self, payload: str, **kwargs) -> str:
        """Place the payload on this surface; return a reference
        (URL, file path, doc id, tool id...) for the target to consume.
        """
        ...

    def cleanup(self, reference: str) -> None:
        """Tear down anything created by deliver(), if applicable."""
        ...
