"""Webpage delivery — serves a crafted HTML page (payload hidden in an
HTML comment) via a local http.server instance, for indirect-injection
testing against agents that browse or fetch URLs.

The lab agent (targets/agent_harness.py) has no real browsing tool, so
the orchestrator doesn't fetch this URL over HTTP for the actual test
turn — it reads the rendered page back via read_content() and feeds it
to the agent as "here's the page I fetched for you" (see engine.py).
The page is still served over a real local socket, though: that keeps
this channel honest as infrastructure (a URL a human or a future
browsing-capable target really could fetch) rather than a pure string
template, and makes it a drop-in real delivery surface once a
browsing-capable target is added.
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import tempfile
import threading
import uuid
from pathlib import Path

_TEMPLATE = """<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>
<h1>{title}</h1>
<p>promptfuzzr lab fixture page — served for webpage-delivery testing.</p>
<!-- {payload} -->
</body>
</html>
"""


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002 — matches base signature
        pass  # silence per-request access logs; a fuzz run can serve thousands of these


class WebpageChannel:
    name = "webpage"

    def __init__(self, host: str = "127.0.0.1", base_dir: Path | str | None = None):
        self.host = host
        self.base_dir = Path(base_dir or tempfile.gettempdir()) / "promptfuzzr_web"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._servers: dict[str, socketserver.TCPServer] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._content: dict[str, str] = {}

    def deliver(self, payload: str, title: str = "Lab Fixture Page", **kwargs) -> str:
        """Write a page with `payload` hidden in an HTML comment, serve
        it from a fresh local http.server on an OS-assigned free port
        (port=0), and return the page URL with the page id as a
        fragment so cleanup() and read_content() can find it again.
        """
        page_id = uuid.uuid4().hex[:8]
        page_dir = self.base_dir / page_id
        page_dir.mkdir(parents=True, exist_ok=True)

        html = _TEMPLATE.format(title=title, payload=payload)
        (page_dir / "index.html").write_text(html, encoding="utf-8")
        self._content[page_id] = html

        handler = functools.partial(_QuietHandler, directory=str(page_dir))
        httpd = socketserver.TCPServer((self.host, 0), handler)  # port 0 -> OS picks a free port
        port = httpd.server_address[1]

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        self._servers[page_id] = httpd
        self._threads[page_id] = thread

        return f"http://{self.host}:{port}/index.html#{page_id}"

    def read_content(self, reference: str) -> str:
        """Return the rendered page HTML for `reference` — used to
        build the orchestrator's "here's the page content" trigger
        prompt without requiring the target to actually issue an HTTP
        fetch.
        """
        page_id = reference.rsplit("#", 1)[-1]
        return self._content.get(page_id, "")

    def cleanup(self, reference: str) -> None:
        page_id = reference.rsplit("#", 1)[-1]
        httpd = self._servers.pop(page_id, None)
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        self._threads.pop(page_id, None)
        self._content.pop(page_id, None)