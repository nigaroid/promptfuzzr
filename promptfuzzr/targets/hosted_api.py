"""Text-only target adapter for a hosted API (OpenAI/Anthropic/Replicate
-style). Same degraded-case caveat as local_model.py.

TODO(phase 1): implement a thin wrapper over the relevant SDK, reading
API keys from environment variables only (never hardcode credentials).
"""

from __future__ import annotations

from promptfuzzr.models import ToolCallRecord


class HostedApiTarget:
    target_id = "hosted_api"

    def __init__(self, provider: str, model_name: str):
        self.provider = provider
        self.model_name = model_name

    def send(self, prompt: str, session_id: str | None = None) -> tuple[str, list[ToolCallRecord]]:
        raise NotImplementedError("TODO(phase 1): call the hosted API, return (text, [])")

    def reset_session(self, session_id: str) -> None:
        pass
