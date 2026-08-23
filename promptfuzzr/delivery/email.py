from __future__ import annotations

import subprocess
import uuid


class EmailChannel:
    name = "email"

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def deliver(self, payload: str, **kwargs) -> str:
        to = kwargs.get("to", "lab@promptfuzzr-lab.test")
        subject = kwargs.get("subject", "promptfuzzr lab test")

        body = f"<!-- {payload} -->\n\n<!-- end payload -->"
        reference = f"email-{uuid.uuid4().hex[:8]}"
        self._store[reference] = body

        try:
            subprocess.run(
                [
                    "swaks",
                    "--to", to,
                    "--from", "lab@promptfuzzr-lab.test",
                    "--h-Subject", subject,
                    "--body", body,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            pass

        return reference

    def read_content(self, reference: str) -> str:
        return self._store.get(reference, "")

    def cleanup(self, reference: str) -> None:
        self._store.pop(reference, None)
