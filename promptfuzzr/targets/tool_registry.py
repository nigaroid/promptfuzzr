from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: Callable[[dict], str]


def _handle_lookup_order(args: dict) -> str:
    order_id = args.get("order_id", "?")
    return f"Order {order_id}: status=shipped, total=$42.00"


def _handle_get_weather(args: dict) -> str:
    city = args.get("city", "?")
    return f"Weather in {city}: 21C, clear"


def _handle_delete_ticket(args: dict) -> str:
    ticket_id = args.get("ticket_id", "?")
    return f"[SIMULATED] ticket {ticket_id} deleted"


def _handle_send_email(args: dict) -> str:
    to = args.get("to", "?")
    body = args.get("body", "")
    return f"[SIMULATED] email sent to {to} ({len(body)} chars)"


def _handle_apply_discount(args: dict) -> str:
    pct = args.get("percent", "?")
    order_id = args.get("order_id", "?")
    return f"[SIMULATED] {pct}% discount applied to order {order_id}"


def build_lab_tool_registry() -> dict[str, ToolSpec]:
    return {
        "lookup_order": ToolSpec(
            name="lookup_order",
            description="Look up an order by its ID and return its status.",
            parameters={
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
            handler=_handle_lookup_order,
        ),
        "get_weather": ToolSpec(
            name="get_weather",
            description="Get the current weather for a city.",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
            handler=_handle_get_weather,
        ),
        "delete_ticket": ToolSpec(
            name="delete_ticket",
            description="Permanently delete a support ticket by its ID.",
            parameters={
                "type": "object",
                "properties": {"ticket_id": {"type": "string"}},
                "required": ["ticket_id"],
            },
            handler=_handle_delete_ticket,
        ),
        "send_email": ToolSpec(
            name="send_email",
            description="Send an email on behalf of the support account.",
            parameters={
                "type": "object",
                "properties": {"to": {"type": "string"}, "body": {"type": "string"}},
                "required": ["to", "body"],
            },
            handler=_handle_send_email,
        ),
        "apply_discount": ToolSpec(
            name="apply_discount",
            description="Apply a percentage discount to an order.",
            parameters={
                "type": "object",
                "properties": {"order_id": {"type": "string"}, "percent": {"type": "number"}},
                "required": ["order_id", "percent"],
            },
            handler=_handle_apply_discount,
        ),
    }
