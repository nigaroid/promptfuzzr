from __future__ import annotations

import json
import re
import uuid

from promptfuzzr.targets.model_client import ModelResponse, ModelToolCall


class VulnerableAgentModelClient:
    OUT_OF_SCOPE = ("delete_ticket", "send_email", "apply_discount")

    INJECTION_MARKERS = (
        "ignore previous instructions",
        "disregard all previous",
        "you are now",
        "act as",
        "developer mode",
        "sudo mode",
        "system override",
        "[system]",
        "admin:",
        "---user response---",
        "jailbreak",
    )

    def __init__(self) -> None:
        pass

    @staticmethod
    def _call_id() -> str:
        return f"call-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _stringify(content) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        return json.dumps(content)

    def create(self, system: str, messages: list[dict], tools: list[dict]) -> ModelResponse:
        latest_content = messages[-1].get("content") if messages else None
        message_blob = self._stringify(latest_content)
        descriptions = {t["name"]: t.get("description", "") or "" for t in tools}

        is_first_turn = len(messages) <= 1

        def mentioned(name: str) -> bool:
            if name in message_blob:
                return True
            if not is_first_turn:
                return False
            return any(
                name in desc and other != name for other, desc in descriptions.items()
            )

        victim = next((t for t in self.OUT_OF_SCOPE if mentioned(t)), None)
        if victim is None:
            lowered = message_blob.lower()
            if any(marker in lowered for marker in self.INJECTION_MARKERS):
                m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", message_blob)
                return ModelResponse(
                    text=None,
                    tool_calls=[
                        ModelToolCall(
                            id=self._call_id(),
                            name="send_email",
                            arguments={
                                "to": m.group(0) if m else "attacker@promptfuzzr-lab.test",
                                "body": message_blob[-500:],
                            },
                        )
                    ],
                    stop_reason="tool_use",
                )

            if is_first_turn and "weather" in lowered:
                return ModelResponse(
                    text=None,
                    tool_calls=[
                        ModelToolCall(
                            id=self._call_id(), name="get_weather", arguments={"city": "Paris"}
                        )
                    ],
                    stop_reason="tool_use",
                )
            return ModelResponse(
                text="How can I help you with your order today?",
                tool_calls=[],
                stop_reason="end_turn",
            )

        args: dict = {}
        if victim == "delete_ticket":
            m = re.search(r"ticket[_ -]?(\d+)", message_blob, re.IGNORECASE)
            args["ticket_id"] = m.group(1) if m else "42"
        elif victim == "send_email":
            m = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", message_blob)
            args["to"] = m.group(0) if m else "attacker@promptfuzzr-lab.test"
            args["body"] = message_blob[-500:]
        elif victim == "apply_discount":
            m = re.search(r"(\d+)\s*%", message_blob)
            args["percent"] = int(m.group(1)) if m else 20
            args["order_id"] = "A-1024"

        return ModelResponse(
            text=None,
            tool_calls=[ModelToolCall(id=self._call_id(), name=victim, arguments=args)],
            stop_reason="tool_use",
        )
