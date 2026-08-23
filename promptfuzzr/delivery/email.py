"""
Sends a crafted HTML email (payload hidden in an
HTML comment) to a lab inbox via swaks, for agents with email-reading
tools.

Unlike webpage/file/rag_doc, there's no real inbox this channel can
poll back from (that would need a live mail server + IMAP client,
which is out of scope for a controlled lab fixture). So the delivered
body is kept in an in-memory store keyed by reference, exactly the way
a lab fixture should behave: read_content() always returns what was
actually delivered, regardless of whether the swaks send itself
succeeded, failed, or swaks isn't installed at all. The swaks call is
attempted for realism/logging only -- it is never load-bearing for
whether the test case can be judged correctly.
"""

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
