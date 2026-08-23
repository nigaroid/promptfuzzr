from __future__ import annotations


class DirectChannel:
    name = "direct"

    def deliver(self, payload: str, **kwargs) -> str:
        return payload

    def cleanup(self, reference: str) -> None:
        pass  # nothing was created, nothing to tear down
