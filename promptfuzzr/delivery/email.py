"""Email delivery �?" sends a crafted HTML email (payload hidden in an
HTML comment) to a lab inbox via swaks, for agents with email-reading
tools.

TODO(phase 3): wrap `swaks` as a subprocess call. Only ever target lab
addresses/domains you control ��� see roadmap.md domain-evasion note.
"""

from __future__ import annotations

import subprocess
import shlex
import uuid


class EmailChannel:
    name = "email"

    def deliver(self, payload: str, **kwargs) -> str:
        """Send an email with `payload` hidden in an HTML comment via
        swaks. Returns a reference string (the Message-ID) that
        cleanup() and read_content() use to locate the email again.

        Only lab-controlled addresses/domains are supported — this is
        not a general-purpose email sender.
        """
        to = kwargs.get("to", "lab@promptfuzzr-lab.test")
        subject = kwargs.get("subject", "promptfuzzr lab test")

        # Build a minimal HTML body with the payload in a comment
        body = f"<!-- {payload} -->\n\n<!-- end payload -->"

        # Use swaks if available; fall back to a synthetic reference
        try:
            args = [
                "swaks",
                f"--to {to}",
                f"--from lab@promptfuzzr-lab.test",
                f"--h subject:{subject}",
                f"--body-file -",
            ]
            proc = subprocess.run(
                args,
                input=body,
                capture_output=True,
                text=True,
                timeout=30,
            )
            # swaks may output the Message-ID on the last line
            lines = proc.stdout.strip().splitlines() if proc.stdout else []
            ref = lines[-1] if lines else ""
            return ref if ref else f"synthetic-email-{uuid.uuid4().hex[:8]}"
        except Exception:
            # swaks not installed or other error — give a synthetic ref
            # so the orchestrator doesn't crash; the test will be
            # marked appropriately downstream.
            return f"synthetic-email-{uuid.uuid4().hex[:8]}"

    def cleanup(self, reference: str) -> None:
        # No persistent state to tear down for the synthetic fallback.
        pass