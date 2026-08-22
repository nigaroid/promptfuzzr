"""Email delivery -- sends a crafted HTML email (payload hidden in an
HTML comment) to a lab inbox via swaks, for agents with email-reading
tools.

Only ever target lab addresses/domains you control -- see roadmap.md
domain-evasion note.

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
        """"Send" an email with `payload` hidden in an HTML comment.
        Returns a reference string that cleanup() and read_content()
        use to locate the body again.

        Only lab-controlled addresses/domains are supported -- this is
        not a general-purpose email sender.
        """
        to = kwargs.get("to", "lab@promptfuzzr-lab.test")
        subject = kwargs.get("subject", "promptfuzzr lab test")

        body = f"<!-- {payload} -->\n\n<!-- end payload -->"
        reference = f"email-{uuid.uuid4().hex[:8]}"
        self._store[reference] = body

        # Best-effort real send via swaks, for anyone actually running a
        # lab mail server to inspect delivery end-to-end. Each flag and
        # its value MUST be separate argv entries -- subprocess.run()
        # without shell=True does not split "--to value" into two
        # arguments the way a shell would; passing them pre-joined sends
        # swaks a single malformed argument.
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
            # swaks not installed, or the send failed -- fine. The
            # reference above already has the body available for
            # read_content(), so the test case is still meaningful.
            pass

        return reference

    def read_content(self, reference: str) -> str:
        """Read back the delivered body -- used by the orchestrator to
        build the "I just received this email" trigger prompt.
        """
        return self._store.get(reference, "")

    def cleanup(self, reference: str) -> None:
        self._store.pop(reference, None)
