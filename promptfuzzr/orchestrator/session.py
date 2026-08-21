"""Session state for multi-turn and kill-chain test cases.

TODO(phase 4): implement Session, tracking:
  - conversation history for multi_step propagation (Study 10)
  - cumulative tool_calls for kill-chain depth measurement (Study 11)
  - the AuthorityPolicy in effect, for the action-outcome judge
"""

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
        """How many chained tool calls this session has triggered so far
        — used as a severity metric per roadmap.md Study 11.
        """
        raise NotImplementedError("TODO(phase 4): count consecutive attacker-triggered calls")
