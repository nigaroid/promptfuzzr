from __future__ import annotations

import os
from pathlib import Path

PROMPTFUZZR_HOME = Path.home() / ".promptfuzzr"
DB_DIR = PROMPTFUZZR_HOME / "db"

_OVERRIDE_ENV_VAR = "PROMPTFUZZR_DB_DIR"


def get_db_path(name: str = "promptfuzzr.db") -> Path:
    base_dir = Path(os.environ[_OVERRIDE_ENV_VAR]) if _OVERRIDE_ENV_VAR in os.environ else DB_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / name
