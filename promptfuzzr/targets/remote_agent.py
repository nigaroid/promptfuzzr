"""Remote agent target: talks to an EXTERNAL agent exposing an
OpenAI-compatible /v1/chat/completions endpoint — e.g. DVAA's agent
fleet (LegacyBot :7003, HelperBot :7002, RAGBot :7005), or any other
chat-completions-shaped agent under test.

Unlike AgentHarnessTarget (where WE own the tool registry and observe
tool calls we asked for), a remote agent brings its own system prompt,
tools, and behavior. We manage per-session history ourselves, post the
user turn, and record whatever comes back:

- tool_calls in the response -> real ToolCallRecord entries, so the
  action-outcome judge works when the backend emits structured calls
  (e.g. DVAA in live-LLM mode).
- text-only responses (DVAA's default simulated mode describes actions
  in prose like "ticket deleted") -> empty trace; verdicts then come
  from the heuristic judge, whose technique indicator patterns cover
  exactly those action-confirmations.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from urllib import error as urlerror
from urllib import request as urlrequest

from promptfuzzr.models import ToolCallRecord


class RemoteAgentTarget:
    """Send()-compatible target backed by a remote OpenAI-compatible
    agent endpoint. Satisfies the same structural interface the
    orchestrator expects from AgentHarnessTarget: target_id, send(),
    reset_session().
    """

    def __init__(self, endpoint: str, model: str = "agent", timeout: float = 60.0):
        self.endpoint = endpoint.rstrip("/")
        if not self.endpoint.endswith("/chat/completions"):
            self.endpoint += "/v1/chat/completions"
        self.model = model
        self.timeout = timeout
        self.target_id = f"remote:{self.endpoint}"
        self._sessions: dict[str, list[dict]] = {}

    def reset_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def send(self, prompt: str, session_id: str | None = None) -> tuple[str, list[ToolCallRecord]]:
        session_id = session_id or "default"
        history = self._sessions.setdefault(session_id, [])
        history.append({"role": "user", "content": prompt})

        payload = json.dumps(
            {"model": self.model, "messages": history, "max_tokens": 1024}
        ).encode()
        req = urlrequest.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode())
        except urlerror.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise RuntimeError(f"remote agent HTTP {exc.code}: {detail}") from exc
        except urlerror.URLError as exc:
            raise RuntimeError(
                f"cannot reach remote agent at {self.endpoint}: {exc.reason}"
            ) from exc

        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""

        trace: list[ToolCallRecord] = []
        order = 0
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
                if not isinstance(args, dict):
                    args = {}
            except (json.JSONDecodeError, TypeError):
                args = {}
            order += 1
            trace.append(
                ToolCallRecord(
                    tool_name=fn.get("name", "?"),
                    arguments=args,
                    authorized=False,  # placeholder — judged later
                    order=order,
                    timestamp=datetime.now(timezone.utc),
                )
            )

        history.append({"role": "assistant", "content": text})
        return text, trace


def probe_endpoint(endpoint: str, timeout: float = 10.0) -> bool:
    """Cheap liveness check: POST a tiny message, return True on any
    well-formed chat.completions response. Used by the CLI to fail fast
    with a readable error before launching a full fuzz run.
    """
    target = RemoteAgentTarget(endpoint=endpoint, timeout=timeout)
    try:
        target.send("ping", session_id=f"probe-{uuid.uuid4().hex[:8]}")
        return True
    except RuntimeError:
        return False