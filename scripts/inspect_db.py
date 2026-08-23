import sqlite3
import sys

from promptfuzzr.storage.paths import get_db_path

db_path = sys.argv[1] if len(sys.argv) > 1 else str(get_db_path())

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print(f"=== runs in {db_path} ===")
for row in conn.execute("SELECT run_id, target_id, started_at, finished_at FROM runs"):
    print(dict(row))

print()
print("=== test_cases summary (by verdict) ===")
for row in conn.execute("SELECT verdict, COUNT(*) as n FROM test_cases GROUP BY verdict"):
    print(f"  {row['verdict']}: {row['n']}")

print()
print("=== test_cases detail ===")
for row in conn.execute(
    "SELECT technique, verdict, verdict_basis, retry_count, response_text, notes FROM test_cases"
):
    print(f"[{row['verdict']:8s}] {row['technique']:30s} basis={row['verdict_basis']:15s} retries={row['retry_count']}")
    if row["verdict"] == "error":
        print(f"           notes: {row['notes']}")
    elif row["response_text"]:
        preview = row["response_text"][:100].replace("\n", " ")
        print(f"           response: {preview}...")
