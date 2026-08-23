from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

_TEMPLATES: dict[str, str] = {
    "txt": "Support ticket notes\n---------------------\n{payload}\n",
    "md": "# Meeting notes\n\n- Reviewed open items\n- {payload}\n- Next sync: Thursday\n",
    "csv": (
        "row_id,customer,note\n"
        "1,Acme Corp,\"Standard renewal, no issues.\"\n"
        '2,Globex Inc,"{payload}"\n'
        "3,Initech,\"Follow up next quarter.\"\n"
    ),
    "code": (
        "# utils.py\n"
        "# TODO: clean up before merge\n"
        "# {payload}\n"
        "def helper():\n"
        "    return None\n"
    ),
}

_EXTENSIONS: dict[str, str] = {"txt": "txt", "md": "md", "csv": "csv", "code": "py"}


class FileChannel:
    name = "file"

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir or tempfile.gettempdir()) / "promptfuzzr_files"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def deliver(self, payload: str, file_type: str = "txt", **kwargs) -> str:
        if file_type not in _TEMPLATES:
            raise ValueError(f"unknown file_type '{file_type}' — expected one of {list(_TEMPLATES)}")

        content = _TEMPLATES[file_type].format(payload=payload)
        ext = _EXTENSIONS[file_type]
        path = self.base_dir / f"{uuid.uuid4().hex}.{ext}"
        path.write_text(content, encoding="utf-8")
        return str(path)

    def read_content(self, reference: str) -> str:
        return Path(reference).read_text(encoding="utf-8")

    def cleanup(self, reference: str) -> None:
        Path(reference).unlink(missing_ok=True)