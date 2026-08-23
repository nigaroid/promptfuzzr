from __future__ import annotations

import uuid


class ToolSchemaChannel:
    name = "tool_schema"

    def __init__(self) -> None:
        self._patches: dict[str, tuple[dict, str, str]] = {}

    def deliver(
        self,
        payload: str,
        tool_registry: dict | None = None,
        target_tool_name: str = "get_weather",
        mode: str = "replace",
        **kwargs,
    ) -> str:
        if tool_registry is None:
            raise ValueError("tool_schema delivery requires a `tool_registry` kwarg")

        spec = tool_registry.get(target_tool_name)
        if spec is None:
            raise KeyError(
                f"tool_schema delivery: '{target_tool_name}' is not in the "
                f"supplied tool_registry (available: {sorted(tool_registry)})"
            )

        original_description = spec.description

        if mode == "replace":
            spec.description = payload
        elif mode == "append":
            spec.description = f"{spec.description} {payload}"
        else:
            raise ValueError(f"tool_schema delivery: unknown mode '{mode}' (use 'replace' or 'append')")

        reference = f"tool_schema:{target_tool_name}:{uuid.uuid4().hex[:8]}"
        self._patches[reference] = (tool_registry, target_tool_name, original_description)
        return reference

    def cleanup(self, reference: str) -> None:
        patch = self._patches.pop(reference, None)
        if patch is None:
            return
        tool_registry, target_tool_name, original_description = patch
        spec = tool_registry.get(target_tool_name)
        if spec is not None:
            spec.description = original_description