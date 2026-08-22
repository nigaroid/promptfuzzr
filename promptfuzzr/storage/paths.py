"""Single source of truth for where promptfuzzr's SQLite database lives.

The database location is an APPLICATION concern, not a per-run config
concern -- it must never be set via a YAML config file, a CLI flag, or
hardcoded relative to the current working directory or the repo. Every
other module that needs a database path calls get_db_path() from here;
nothing else in the codebase should construct or hardcode one.

Layout (identical logic on every OS -- Path.home() resolves the
platform-correct home directory, no manual path-separator handling
needed):

    Linux:   /home/<user>/.promptfuzzr/db/
    Windows: C:\\Users\\<user>\\.promptfuzzr\\db\\
    macOS:   /Users/<user>/.promptfuzzr/db/
"""

from __future__ import annotations

import os
from pathlib import Path

PROMPTFUZZR_HOME = Path.home() / ".promptfuzzr"
DB_DIR = PROMPTFUZZR_HOME / "db"

# The ONE sanctioned override mechanism, and it exists for exactly one
# reason: automated tests need to write to an isolated temp directory
# instead of the real ~/.promptfuzzr/db/, without polluting a real
# user's data or leaking state between test runs. This is intentionally
# NOT a YAML field or a CLI flag -- an environment variable set only by
# test harnesses (see tests/test_storage_paths.py and
# scripts/verify_phases.py) is the narrowest possible surface for this,
# and no application code (cli.py, engine.py, ...) needs to know it
# exists; they all just call get_db_path() plain.
_OVERRIDE_ENV_VAR = "PROMPTFUZZR_DB_DIR"


def get_db_path(name: str = "promptfuzzr.db") -> Path:
    """Return the path promptfuzzr's SQLite database should live at,
    creating the containing directory if it doesn't exist yet.

    `name` lets a caller pick the filename (e.g. a diagnostic script
    inspecting a specific file) -- it never lets a caller pick the
    directory. The directory is always DB_DIR (~/.promptfuzzr/db/),
    except under the test-only environment-variable override described
    above.
    """
    base_dir = Path(os.environ[_OVERRIDE_ENV_VAR]) if _OVERRIDE_ENV_VAR in os.environ else DB_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / name
