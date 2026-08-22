"""Thin SQLite persistence layer over schema.sql.

save_test_case / load_test_cases are implemented now (pure serialization,
no design decisions pending). start_run / finish_run are left for Phase 1
since they depend on how orchestrator/engine.py wants to generate run_ids.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from promptfuzzr.models import (
    Delivery,
    Encoding,
    Propagation,
    Technique,
    TestCase,
    ToolCallRecord,
    Verdict,
    VerdictBasis,
)
from promptfuzzr.storage.paths import get_db_path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite DB at db_path and ensure the
    schema exists. Safe to call repeatedly — schema.sql uses
    CREATE TABLE IF NOT EXISTS throughout.

    db_path defaults to get_db_path() — the centralized, platform-
    independent application database location (~/.promptfuzzr/db/).
    Passing an explicit db_path is for test fixtures that need an
    isolated file; production code should call init_db() with no
    argument.

    Also applies additive migrations for columns added after Phase 0
    (CREATE TABLE IF NOT EXISTS won't touch an existing table). Each
    migration is a try/ignore ALTER TABLE: if the column already exists
    the ALTER fails with OperationalError and that's fine.
    """
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA_PATH.read_text())
    for stmt in (
        "ALTER TABLE test_cases ADD COLUMN kill_chain_depth INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already present
    conn.commit()
    return conn


def save_test_case(conn: sqlite3.Connection, run_id: str, test_case: TestCase) -> None:
    """Insert or replace a TestCase row. Enum fields are stored as their
    .value; list/dict fields are stored as JSON.
    """
    tool_calls_json = json.dumps(
        [
            {
                "tool_name": tc.tool_name,
                "arguments": tc.arguments,
                "authorized": tc.authorized,
                "order": tc.order,
                "timestamp": tc.timestamp.isoformat(),
            }
            for tc in test_case.tool_calls
        ]
    )

    conn.execute(
        """
        INSERT OR REPLACE INTO test_cases (
            id, run_id, technique, delivery, propagation, encoding,
            payload, mutation_chain_json, target_id, response_text,
            tool_calls_json, verdict, verdict_basis, confidence,
            retry_count, kill_chain_depth, minimized_payload, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            test_case.id,
            run_id,
            test_case.technique.value,
            test_case.delivery.value,
            test_case.propagation.value,
            test_case.encoding.value,
            test_case.payload,
            json.dumps(test_case.mutation_chain),
            test_case.target_id,
            test_case.response_text,
            tool_calls_json,
            test_case.verdict.value,
            test_case.verdict_basis.value,
            test_case.confidence,
            test_case.retry_count,
            test_case.kill_chain_depth,
            test_case.minimized_payload,
            test_case.notes,
        ),
    )
    conn.commit()


def _row_to_test_case(row: sqlite3.Row) -> TestCase:
    tool_calls = [
        ToolCallRecord(
            tool_name=tc["tool_name"],
            arguments=tc["arguments"],
            authorized=tc["authorized"],
            order=tc["order"],
        )
        for tc in json.loads(row["tool_calls_json"])
    ]
    return TestCase(
        id=row["id"],
        technique=Technique(row["technique"]),
        delivery=Delivery(row["delivery"]),
        propagation=Propagation(row["propagation"]),
        encoding=Encoding(row["encoding"]),
        payload=row["payload"],
        mutation_chain=json.loads(row["mutation_chain_json"]),
        target_id=row["target_id"],
        response_text=row["response_text"],
        tool_calls=tool_calls,
        verdict=Verdict(row["verdict"]),
        verdict_basis=VerdictBasis(row["verdict_basis"]),
        confidence=row["confidence"],
        retry_count=row["retry_count"],
        kill_chain_depth=row["kill_chain_depth"],
        minimized_payload=row["minimized_payload"],
        notes=row["notes"] or "",
    )


def load_test_cases(conn: sqlite3.Connection, run_id: str, verdict: str | None = None) -> list[TestCase]:
    """Load all TestCases for a run, optionally filtered by verdict
    (e.g. "success" — used by cli.py::findings).
    """
    conn.row_factory = sqlite3.Row
    if verdict:
        cursor = conn.execute(
            "SELECT * FROM test_cases WHERE run_id = ? AND verdict = ?", (run_id, verdict)
        )
    else:
        cursor = conn.execute("SELECT * FROM test_cases WHERE run_id = ?", (run_id,))
    return [_row_to_test_case(row) for row in cursor.fetchall()]
