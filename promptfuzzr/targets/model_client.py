"""The ModelClient abstraction — decouples AgentHarnessTarget's
tool-calling loop from any specific LLM provider. Every concrete
client (Anthropic, OpenAI-compatible, the deterministic vulnerable
positive-control) implements .create() and returns the same
normalized ModelResponse shape, so the loop itself never needs to know
which provider it's talking to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ModelToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ModelResponse:
    """Normalized shape every ModelClient implementation returns,
    regardless of provider-specific response formats.
    """

    text: str | None
    tool_calls: list[ModelToolCall] = field(default_factory=list)
    stop_reason: str = ""


class ModelClient(Protocol):
    def create(self, system: str, messages: list[dict], tools: list[dict]) -> ModelResponse:
        """One model turn: given the system prompt, message history, and
        available tool definitions, return either a text response or a
        request to call one or more tools (never both, per Anthropic's
        tool-use API shape — a turn either finishes or asks for tools).
        """
        ...
