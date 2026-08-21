"""OpenAICompatibleModelClient — ModelClient for any OpenAI-compatible
chat completions API (local routers: LiteLLM proxy, text-generation-
webui, vLLM's OpenAI server, LM Studio, omniroute, etc.).
"""

from __future__ import annotations

from typing import Any, cast

from promptfuzzr.targets.model_client import ModelResponse, ModelToolCall


class OpenAICompatibleModelClient:
    """ModelClient for any OpenAI-compatible chat completions API — the
    standard shape exposed by local model routers (LiteLLM proxy,
    text-generation-webui, vLLM's OpenAI server, LM Studio, and similar
    tools including omniroute). Reads the API key from
    OPENAI_COMPAT_API_KEY and the endpoint from OPENAI_COMPAT_BASE_URL
    — never hardcode either.

    Tool-calling support is NOT guaranteed by every backend behind
    these routers. If the underlying model doesn't honor the `tools`
    param, you'll typically see either (a) an API error, or (b) the
    call succeeds but the model just never produces a tool_calls block
    and instead describes what it would do in plain text. This class
    doesn't try to paper over that — probe the model with
    scripts/probe_tool_calling.py before relying on this in a real fuzz
    run, since a model that only *talks about* calling tools instead of
    actually calling them would make every test case fall through to
    the heuristic judge instead of action_outcome, silently defeating
    the differentiator.
    """

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

        # OpenAI's chat.completions API takes the system prompt as a
        # message, not a separate top-level param the way Anthropic's
        # does — normalize that here rather than pushing this
        # provider-specific detail up into agent_harness's loop.
        #
        # The harness history stores provider-neutral blocks shaped like
        # Anthropic's API (assistant turns carry {"type": "tool_use"}
        # content items; tool results ride in a user turn as
        # {"type": "tool_result"} items). Strict OpenAI-compatible
        # endpoints reject that shape, so translate it here:
        #   assistant tool_use items -> {"role": "assistant", "tool_calls": [...]}
        #   user tool_result items   -> one {"role": "tool", ...} message each
        oai_messages: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            role = m.get("role")
            content = m.get("content")

            if isinstance(content, str):
                oai_messages.append({"role": role, "content": content})
                continue

            # Content is a block list — split it by type.
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
                # OpenAI represents each tool result as its own "tool"
                # message tied to the originating call id.
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

        # Translate the generic {name, description, parameters} shape
        # into OpenAI's {"type": "function", "function": {...}}.
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

        # cast(Any, ...) keeps strict type checkers (Pylance/pyright) quiet
        # on this call: the SDK declares Iterable[ChatCompletion*Param]
        # unions here, and hand-built plain dicts don't statically match
        # those types even though they satisfy them at runtime. The shapes
        # above are exactly what the SDK expects; this is annotation-only.
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
                    # Some backends return malformed or already-parsed
                    # arguments — don't crash the whole run over it,
                    # surface it as an empty-args call instead so the
                    # judge still sees SOMETHING was attempted.
                    arguments = {}
                tool_calls.append(
                    ModelToolCall(id=call.id, name=call.function.name, arguments=arguments)
                )

        return ModelResponse(
            text=message.content,
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason or "",
        )
