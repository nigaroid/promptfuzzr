from __future__ import annotations

from promptfuzzr.models import ToolCallRecord
from promptfuzzr.targets.anthropic_client import AnthropicModelClient
from promptfuzzr.targets.model_client import ModelClient, ModelResponse, ModelToolCall
from promptfuzzr.targets.openai_compat_client import OpenAICompatibleModelClient
from promptfuzzr.targets.tool_registry import ToolSpec, build_lab_tool_registry
from promptfuzzr.targets.vulnerable_client import VulnerableAgentModelClient

__all__ = [
    "AgentHarnessTarget",
    "AnthropicModelClient",
    "ModelClient",
    "ModelResponse",
    "ModelToolCall",
    "OpenAICompatibleModelClient",
    "ToolSpec",
    "VulnerableAgentModelClient",
    "build_lab_tool_registry",
]


class AgentHarnessTarget:
    target_id = "lab_agent"

    def __init__(
        self,
        model_client: ModelClient,
        tool_registry: dict[str, ToolSpec] | None = None,
        system_prompt: str = "You are a helpful customer support assistant.",
        max_tool_iterations: int = 8,
    ):
        self.model_client = model_client
        self.tool_registry = tool_registry or build_lab_tool_registry()
        self.system_prompt = system_prompt
        self.max_tool_iterations = max_tool_iterations
        self._sessions: dict[str, list[dict]] = {}

    def _tool_definitions(self) -> list[dict]:
        return [
            {"name": spec.name, "description": spec.description, "parameters": spec.parameters}
            for spec in self.tool_registry.values()
        ]

    def send(self, prompt: str, session_id: str | None = None) -> tuple[str, list[ToolCallRecord]]:
        session_id = session_id or "default"
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": "user", "content": prompt})

        trace: list[ToolCallRecord] = []
        order = 0

        for _ in range(self.max_tool_iterations):
            response = self.model_client.create(
                system=self.system_prompt,
                messages=history,
                tools=self._tool_definitions(),
            )

            if not response.tool_calls:
                final_text = response.text or ""
                history.append({"role": "assistant", "content": final_text})
                return final_text, trace

            assistant_content = []
            tool_result_content = []

            for call in response.tool_calls:
                order += 1
                trace.append(
                    ToolCallRecord(
                        tool_name=call.name,
                        arguments=call.arguments,
                        authorized=False,
                        order=order,
                    )
                )

                assistant_content.append(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                )

                spec = self.tool_registry.get(call.name)
                if spec is None:
                    result_text = f"[error] unknown tool '{call.name}'"
                else:
                    result_text = spec.handler(call.arguments)

                tool_result_content.append(
                    {"type": "tool_result", "tool_use_id": call.id, "content": result_text}
                )

            history.append({"role": "assistant", "content": assistant_content})
            history.append({"role": "user", "content": tool_result_content})

        return "[error] max_tool_iterations exceeded", trace

    def reset_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
