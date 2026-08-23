from __future__ import annotations

from typing import Any, cast

from promptfuzzr.targets.model_client import ModelResponse, ModelToolCall


class OpenAICompatibleModelClient:
    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        max_tokens: int = 1024,
    ):
        import openai  # imported lazily so importing this module doesn't require the SDK
        import os

        self._client = openai.OpenAI(
            api_key=os.environ.get("OPENAI_COMPAT_API_KEY", "not-needed-for-local-router"),
            base_url=base_url or os.environ.get("OPENAI_COMPAT_BASE_URL"),
        )
        self.model = model
        self.max_tokens = max_tokens

    def create(self, system: str, messages: list[dict], tools: list[dict]) -> ModelResponse:
        import json

        oai_messages: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            role = m.get("role")
            content = m.get("content")

            if isinstance(content, str):
                oai_messages.append({"role": role, "content": content})
                continue

            text_parts: list[str] = []
            tool_calls_out: list[dict] = []
            tool_results: list[dict] = []
            for block in content or []:
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    tool_calls_out.append(
                        {
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block.get("input") or {}),
                            },
                        }
                    )
                elif btype == "tool_result":
                    tool_results.append(block)
                else:
                    text_parts.append(json.dumps(block))

            if role == "assistant":
                msg: dict = {
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else None,
                }
                if tool_calls_out:
                    msg["tool_calls"] = tool_calls_out
                oai_messages.append(msg)
            elif tool_results:
                for tr in tool_results:
                    result_content = tr.get("content")
                    if not isinstance(result_content, str):
                        result_content = json.dumps(result_content)
                    oai_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tr.get("tool_use_id", ""),
                            "content": result_content,
                        }
                    )
                for extra_text in text_parts:
                    oai_messages.append({"role": "user", "content": extra_text})
            else:
                oai_messages.append(
                    {"role": role, "content": "\n".join(text_parts)}
                )

        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]

        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=cast(Any, oai_messages),
            tools=cast(Any, oai_tools) if oai_tools else None,
        )

        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for call in message.tool_calls:
                try:
                    arguments = json.loads(call.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
                tool_calls.append(
                    ModelToolCall(id=call.id, name=call.function.name, arguments=arguments)
                )

        return ModelResponse(
            text=message.content,
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason or "",
        )
