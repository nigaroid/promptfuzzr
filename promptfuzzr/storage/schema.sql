-- promptfuzzr SQLite schema
-- TODO(phase 0): review/extend once orchestrator/engine.py and
-- report/ solidify their query patterns.

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    target_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    config_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS test_cases (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    technique TEXT NOT NULL,
    delivery TEXT NOT NULL,
    propagation TEXT NOT NULL,
    encoding TEXT NOT NULL,
    payload TEXT NOT NULL,
    mutation_chain_json TEXT NOT NULL,
    target_id TEXT NOT NULL,
    response_text TEXT,
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    verdict TEXT NOT NULL,
    verdict_basis TEXT NOT NULL,
    confidence REAL NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    kill_chain_depth INTEGER NOT NULL DEFAULT 0,
    minimized_payload TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_test_cases_run_id ON test_cases(run_id);
CREATE INDEX IF NOT EXISTS idx_test_cases_verdict ON test_cases(verdict);
CREATE INDEX IF NOT EXISTS idx_test_cases_technique ON test_cases(technique);
