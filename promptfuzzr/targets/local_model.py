"""Text-only target adapter for a local model (e.g. via Ollama). No
tool-calling loop — tool_calls is always []. Treated as the degraded
case per roadmap.md section 0 (action-outcome judging needs a target
with real tools; this adapter falls back to heuristic/LLM-judge only).

TODO(phase 1): implement a thin wrapper over the ollama HTTP API.
"""

from __future__ import annotations

from promptfuzzr.models import ToolCallRecord


class LocalModelTarget:
    target_id = "local_model"

    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def send(self, prompt: str, session_id: str | None = None) -> tuple[str, list[ToolCallRecord]]:
        raise NotImplementedError("TODO(phase 1): call the local model, return (text, [])")

    def reset_session(self, session_id: str) -> None:
        pass
