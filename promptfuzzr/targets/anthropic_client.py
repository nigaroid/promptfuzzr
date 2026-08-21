"""AnthropicModelClient — thin wrapper over the real Anthropic SDK."""

from __future__ import annotations

from promptfuzzr.targets.model_client import ModelResponse, ModelToolCall


class AnthropicModelClient:
    """Thin wrapper over the real Anthropic SDK. Reads the API key from
    the ANTHROPIC_API_KEY environment variable — never hardcode a key
    here or pass one as a plain argument that could end up logged.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 1024):
        import anthropic  # imported lazily so importing this module doesn't require the SDK

        self._client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens

    def create(self, system: str, messages: list[dict], tools: list[dict]) -> ModelResponse:
        # Translate the generic {name, description, parameters} shape
        # into Anthropic's specific {name, description, input_schema}.
        anthropic_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            tools=anthropic_tools,
        )

        text_parts = [block.text for block in response.content if block.type == "text"]
        tool_calls = [
            ModelToolCall(id=block.id, name=block.name, arguments=block.input)
            for block in response.content
            if block.type == "tool_use"
        ]

        return ModelResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "",
        )
