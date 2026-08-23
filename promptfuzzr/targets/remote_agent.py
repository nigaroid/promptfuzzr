from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from urllib import error as urlerror
from urllib import request as urlrequest

from promptfuzzr.models import ToolCallRecord


class RemoteAgentTarget:
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
                    authorized=False,
                    order=order,
                    timestamp=datetime.now(timezone.utc),
                )
            )

        history.append({"role": "assistant", "content": text})
        return text, trace


def probe_endpoint(endpoint: str, timeout: float = 10.0) -> bool:
    target = RemoteAgentTarget(endpoint=endpoint, timeout=timeout)
    try:
        target.send("ping", session_id=f"probe-{uuid.uuid4().hex[:8]}")
        return True
    except RuntimeError:
        return False