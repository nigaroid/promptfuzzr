"""Common interface every target adapter implements.

send() must return both the text response AND the full tool-call trace
(list[ToolCallRecord]) — even an empty list for text-only targets —
so the orchestrator and judge always have a consistent shape to work
with. This is what makes action-outcome judging possible; don't let a
target adapter collapse this down to text-only.
"""

from __future__ import annotations

from typing import Protocol

from promptfuzzr.models import ToolCallRecord


class TargetAdapter(Protocol):
    target_id: str

    def send(self, prompt: str, session_id: str | None = None) -> tuple[str, list[ToolCallRecord]]:
        """Send prompt to the target, return (response_text, tool_calls)."""
        ...

    def reset_session(self, session_id: str) -> None:
        """Clear a session's history, if the target is stateful."""
        ...
