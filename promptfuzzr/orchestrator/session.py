from __future__ import annotations

from dataclasses import dataclass, field

from promptfuzzr.config import AuthorityPolicy
from promptfuzzr.models import ToolCallRecord


@dataclass
class Session:
    session_id: str
    authority_policy: AuthorityPolicy
    history: list[str] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    def kill_chain_depth(self) -> int:
        raise NotImplementedError("TODO(phase 4): count consecutive attacker-triggered calls")
