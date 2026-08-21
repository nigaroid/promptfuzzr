"""Tool-schema / tool-definition delivery — promptfuzzr's differentiator
surface (see roadmap.md section 0). Injects the payload into a tool's
`description` field in the target's tool registry, so it's fed into
the model's context on every turn regardless of whether the tool is
ever called.

This is the highest-priority delivery module — it's the headline
"nobody else tests this" surface.
"""

from __future__ import annotations

import uuid


class ToolSchemaChannel:
    """Poisons a tool's `description` field in-place inside a
    caller-supplied tool registry (a `dict[str, ToolSpec]`, e.g.
    `target.tool_registry` from targets/agent_harness.py).

    Deliberately takes the registry as an explicit kwarg rather than a
    whole target/adapter object, so this channel can be exercised
    against any dict-shaped registry (real or a test fixture) without
    depending on AgentHarnessTarget specifically — same reasoning as
    delivery/rag_doc.py taking a rag_store instead of a full target.

    The DeliveryChannel protocol's cleanup() only takes a reference
    string, not the registry — so each `deliver()` call's before-state
    is kept on the instance, keyed by the reference it returns, and
    cleanup() looks it up from there.
    """

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
        """Poison `tool_registry[target_tool_name].description`.

        `mode`:
          - "replace" (default): the tool's description becomes exactly
            `payload`. Matches the shape of corpus/seeds/schema_seeds.yaml,
            where base_text is already a full, plausible-looking
            description with the imperative folded in.
          - "append": `payload` is appended after the tool's existing
            description, separated by a space — useful for testing
            whether a payload needs to *look* like the whole doc or can
            just be tacked onto a legitimate one.

        Returns a reference string (not the tool name itself, so
        multiple concurrent patches of the same tool across parallel
        test cases don't collide) that cleanup() uses to restore the
        original description.
        """
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
        """Restore the tool's original description. Safe to call
        multiple times or on an unknown reference — a no-op either way,
        since a fuzz run shouldn't crash on cleanup ordering.
        """
        patch = self._patches.pop(reference, None)
        if patch is None:
            return
        tool_registry, target_tool_name, original_description = patch
        spec = tool_registry.get(target_tool_name)
        if spec is not None:
            spec.description = original_description