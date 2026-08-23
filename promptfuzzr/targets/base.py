from __future__ import annotations

from typing import Protocol

from promptfuzzr.models import ToolCallRecord


class TargetAdapter(Protocol):
    target_id: str

    def send(self, prompt: str, session_id: str | None = None) -> tuple[str, list[ToolCallRecord]]:
        ...

    def reset_session(self, session_id: str) -> None:
        ...
