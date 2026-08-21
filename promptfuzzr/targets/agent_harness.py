"""AgentHarnessTarget — the primary target type: a small lab agent with
a tool-calling loop, decoupled from any specific LLM provider via the
ModelClient protocol (see model_client.py).

This file used to hold everything — tool registry, ModelClient
protocol, all three client implementations, and the loop itself — in
one ~620-line file. It's now split by concern:

    tool_registry.py       ToolSpec + handlers + build_lab_tool_registry()
    model_client.py        ModelToolCall, ModelResponse, ModelClient protocol
    vulnerable_client.py   VulnerableAgentModelClient (positive control)
    anthropic_client.py    AnthropicModelClient
    openai_compat_client.py OpenAICompatibleModelClient
    agent_harness.py       AgentHarnessTarget (this file)

Everything is re-exported below, so existing code that does
`from promptfuzzr.targets.agent_harness import X` for ANY of these
names keeps working unchanged — this file is now also the stable
public entry point, not just the harness.
"""

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
        """Provider-agnostic tool definitions: {name, description,
        parameters} where parameters is a plain JSON schema dict. Each
        ModelClient.create() implementation is responsible for
        translating this into whatever shape its specific API needs
        (Anthropic wants "input_schema"; OpenAI-compatible APIs want it
        nested under "function"). This function must NOT bake in any
        one provider's key names — that was a bug in an earlier draft
        of this file (it emitted "input_schema" directly here), which
        only became visible once a second provider was added.
        """
        return [
            {"name": spec.name, "description": spec.description, "parameters": spec.parameters}
            for spec in self.tool_registry.values()
        ]

    def send(self, prompt: str, session_id: str | None = None) -> tuple[str, list[ToolCallRecord]]:
        """Runs the tool-calling loop: send the prompt, and for as long
        as the model keeps requesting tool calls (up to
        max_tool_iterations, as a safety bound against infinite loops
        — relevant for Study 11's kill-chain-depth measurement later),
        execute each one via the tool registry, record it, and feed the
        result back. Returns once the model responds with plain text.

        History is stored in Anthropic-shaped content blocks
        ({"type": "tool_use"/"tool_result"}) regardless of which
        provider is actually in use — this is the harness's own
        internal representation, not a wire format. Each ModelClient
        implementation (e.g. OpenAICompatibleModelClient) is
        responsible for translating this into whatever shape its
        specific API needs before sending. Keeping ONE internal shape
        here, translated per-provider at the client boundary, is what
        keeps this loop itself provider-agnostic.
        """
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

            # Model requested one or more tool calls — record each,
            # execute it, and prepare the tool-result turn.
            assistant_content = []
            tool_result_content = []

            for call in response.tool_calls:
                order += 1
                trace.append(
                    ToolCallRecord(
                        tool_name=call.name,
                        arguments=call.arguments,
                        authorized=False,  # placeholder — see models.ToolCallRecord docstring
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

        # Safety bound hit without a final text response.
        return "[error] max_tool_iterations exceeded", trace

    def reset_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
