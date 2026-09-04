# Development

## Install development dependencies

```bash
pip install -e ".[dev]"
```

## Run tests

```bash
pytest tests/
```

The current suite contains 58 tests across:

- `tests/test_judge.py`
- `tests/test_minimize.py`
- `tests/test_mutate.py`
- `tests/test_report.py`
- `tests/test_storage_paths.py`

## Working on the fuzzing pipeline

When changing the judge, orchestrator, or seed corpus, validate the pipeline with:

```yaml
target_profile: vulnerable
```

This gives you a deterministic, offline positive control before spending real model/API calls.

## Database

Results are stored in:

```text
~/.promptfuzzr/db/promptfuzzr.db
```

The main tables are `runs` and `test_cases`. Useful columns include:

```text
run_id
target_id
started_at
technique
delivery
propagation
encoding
verdict
verdict_basis
retry_count
kill_chain_depth
tool_calls_json
response_text
minimized_payload
notes
```

A direct query can be run with:

```bash
python3 -c "
import sqlite3
from promptfuzzr.storage.paths import get_db_path
conn = sqlite3.connect(get_db_path())
for row in conn.execute('SELECT run_id, target_id, started_at FROM runs ORDER BY started_at DESC LIMIT 5'):
    print(row)
"
```

## Current implementation caveats

- `axes` is informational only and does not automatically vary runs.
- `concurrency` is defined but execution is currently sequential.
- `partial` is a defined verdict but nothing currently emits it.
- `repo_comment`, `calendar`, and `tool_output` are defined delivery values but currently fall back to `direct`.
- `tool_schema` is implemented only for the local lab agent; remote targets fall back to a benign direct question.
- `cross_session` is implemented meaningfully only with `rag_doc`.
- `minimize` currently supports only `single_shot` findings.
