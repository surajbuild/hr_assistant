"""
scripts/run_tests.py
--------------------
Canonical test runner. Every file in tests/ is a standalone script that prints
[PASS]/[FAIL] lines and exits non-zero on failure (see AGENTS.md §5).

Usage:
    python scripts/run_tests.py                 # run all tests
    python scripts/run_tests.py rag hrms        # run tests whose filename contains any of the words

Requires MySQL from .env with seed data loaded (python scripts/seed_db.py).
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = sorted((ROOT / "tests").glob("test_*.py"))
PASS_RX = re.compile(r"\bPASS\b")
FAIL_RX = re.compile(r"\bFAIL\b")


def main() -> int:
    filters = [a.lower() for a in sys.argv[1:]]
    selected = [t for t in TESTS if not filters or any(f in t.name.lower() for f in filters)]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONWARNINGS": "ignore"}
    total_pass = total_fail = 0
    failed_files = []
    started = time.time()

    for test in selected:
        proc = subprocess.run(
            [sys.executable, str(test)], cwd=ROOT, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        out = proc.stdout + proc.stderr
        passes = sum(1 for line in out.splitlines() if PASS_RX.search(line) and "RESULTS" not in line)
        fails = sum(1 for line in out.splitlines() if FAIL_RX.search(line) and "RESULTS" not in line and "FAILED" not in line)
        ok = proc.returncode == 0 and fails == 0
        total_pass += passes
        total_fail += fails
        status = "OK  " if ok else "FAIL"
        print(f"{status} {test.name:<36} pass={passes:<4} fail={fails:<3} rc={proc.returncode}")
        if not ok:
            failed_files.append(test.name)
            for line in out.splitlines():
                if FAIL_RX.search(line) or "Error" in line:
                    print(f"       {line.strip()[:160]}")

    print("-" * 72)
    print(f"{len(selected)} files | {total_pass} checks passed | {total_fail} failed | {time.time() - started:.1f}s")
    if failed_files:
        print("Failed files: " + ", ".join(failed_files))
    return 1 if failed_files else 0


if __name__ == "__main__":
    sys.exit(main())
