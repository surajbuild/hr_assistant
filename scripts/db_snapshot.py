"""
scripts/db_snapshot.py
----------------------
Fingerprint the dev database (row count + checksum of every row, per table) and
the uploaded-documents folder. Used to prove that the test suite leaves the dev
data untouched (AGENTS.md §5, KNOWN_ISSUES KI-002).

Usage:
    python scripts/db_snapshot.py save before.json
    python scripts/run_tests.py
    python scripts/db_snapshot.py diff before.json        # exit 1 if anything changed

    python scripts/db_snapshot.py isolate                 # run each test file alone and report
                                                          # which ones change the database
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from sqlalchemy import text  # noqa: E402

from app.database.connection import engine  # noqa: E402

TABLES = [
    "employees", "users", "attendance", "leaves", "salary", "documents", "document_chunks", "chat_logs",
    "holidays", "attendance_corrections",
]
DOCUMENTS_DIR = Path(os.getenv("DOCUMENTS_DIR") or ROOT / "documents")


def snapshot() -> dict:
    snap = {}
    with engine.connect() as conn:
        for table in TABLES:
            rows = conn.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
            digest = hashlib.sha256()
            for row in rows:
                digest.update(repr(tuple(row)).encode())
            snap[table] = {
                "count": len(rows),
                "max_id": rows[-1][0] if rows else 0,
                "sha256": digest.hexdigest()[:16],
            }
    files = sorted(p.name for p in DOCUMENTS_DIR.glob("*")) if DOCUMENTS_DIR.exists() else []
    snap["documents_dir"] = {"count": len(files), "sha256": hashlib.sha256("|".join(files).encode()).hexdigest()[:16]}
    return snap


def diff(before: dict, after: dict) -> list[str]:
    changes = []
    for key in before:
        b, a = before[key], after.get(key)
        if b != a:
            changes.append(f"{key}: {b} -> {a}")
    return changes


def isolate() -> int:
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    offenders = 0
    for test in sorted((ROOT / "tests").glob("test_*.py")):
        before = snapshot()
        proc = subprocess.run([sys.executable, str(test)], cwd=ROOT, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        changes = diff(before, snapshot())
        status = "CLEAN " if not changes else "DIRTY "
        print(f"{status}{test.name:<34} rc={proc.returncode}")
        for c in changes:
            print(f"        {c}")
        offenders += bool(changes)
    print(f"\n{offenders} test file(s) changed the database")
    return 1 if offenders else 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "isolate":
        return isolate()
    if len(sys.argv) < 3 or sys.argv[1] not in ("save", "diff"):
        print(__doc__)
        return 2
    path = Path(sys.argv[2])
    if sys.argv[1] == "save":
        path.write_text(json.dumps(snapshot(), indent=2), encoding="utf-8")
        print(f"Snapshot saved to {path}")
        return 0
    changes = diff(json.loads(path.read_text(encoding="utf-8")), snapshot())
    if changes:
        print("Database CHANGED:")
        for c in changes:
            print("  " + c)
        return 1
    print("Database unchanged (all tables + documents folder identical).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
