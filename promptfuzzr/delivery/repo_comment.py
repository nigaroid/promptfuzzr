"""Code-repo delivery — embeds payload as an inline code comment,
targeting coding agents / AI code reviewers.

Writes into a scratch git repo fixture so the surface is realistic
(a real diff/commit an AI code-review agent would be asked to look
at), not just a bare file on disk. One repo fixture is reused across
deliver() calls within a channel instance — each call is a new commit
touching the target file, mirroring how a poisoned comment would
actually arrive in practice (a PR update), which also lets a
propagation=multi_step case build a small commit history if needed.
"""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from pathlib import Path

_GIT_ENV = ["-c", "user.name=promptfuzzr-lab", "-c", "user.email=lab@promptfuzzr-lab.test"]


class RepoCommentChannel:
    name = "repo_comment"

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir or tempfile.gettempdir()) / "promptfuzzr_repos"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._repo_path: Path | None = None

    def _ensure_repo(self) -> Path:
        if self._repo_path is not None and self._repo_path.exists():
            return self._repo_path

        repo = self.base_dir / f"lab_repo_{uuid.uuid4().hex[:8]}"
        repo.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", *_GIT_ENV, "init", "-q"], cwd=repo, check=True)
        self._repo_path = repo
        return repo

    def deliver(self, payload: str, filename: str = "utils.py", **kwargs) -> str:
        """Write `payload` as a code comment block in `filename` inside
        the scratch repo, commit it, and return the file's path (the
        orchestrator reads this back to build the "review this diff"
        trigger prompt — see engine.py).
        """
        repo = self._ensure_repo()
        file_path = repo / filename

        comment_lines = "\n".join(f"# {line}" for line in payload.splitlines()) or f"# {payload}"
        file_path.write_text(
            f"# NOTE for reviewers — please read before merging:\n{comment_lines}\n\n"
            "def helper():\n    return None\n",
            encoding="utf-8",
        )

        subprocess.run(["git", *_GIT_ENV, "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", *_GIT_ENV, "commit", "-q", "-m", f"update {filename}"],
            cwd=repo,
            check=True,
        )
        return str(file_path)

    def read_content(self, reference: str) -> str:
        return Path(reference).read_text(encoding="utf-8")

    def cleanup(self, reference: str) -> None:
        pass  # the repo fixture is a reusable scratch dir; caller may rmtree base_dir if a full reset is wanted