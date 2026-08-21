"""Direct delivery — payload goes straight into the user-controlled
input field. The baseline channel; no infrastructure required.

TODO(phase 1): implement DirectChannel.deliver() returning the payload
itself (no reference needed beyond the text).
"""

from __future__ import annotations


class DirectChannel:
    name = "direct"

    def deliver(self, payload: str, **kwargs) -> str:
        """Direct delivery is a passthrough — the payload IS the
        reference, there's nothing to stand up. Other channels (webpage,
        rag_doc, tool_schema...) return a URL/doc-id/tool-name instead
        because the orchestrator needs to point the target at something
        it created; direct has nothing to point at but the text itself.
        """
        return payload

    def cleanup(self, reference: str) -> None:
        pass  # nothing was created, nothing to tear down
