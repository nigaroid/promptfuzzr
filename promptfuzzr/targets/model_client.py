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
    text: str | None
    tool_calls: list[ModelToolCall] = field(default_factory=list)
    stop_reason: str = ""


class ModelClient(Protocol):
    def create(self, system: str, messages: list[dict], tools: list[dict]) -> ModelResponse:
        ...
