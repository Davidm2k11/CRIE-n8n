#!/usr/bin/env python3
"""
CRIE unified acceptance gate  (Sprint 10, S10-4/S10-8).

Runs every authoritative acceptance suite in the canonical repository layout and
reports a single pass/fail. This is the gate invoked by the CI/CD pipeline
(§200) and by the §406 / §616 production readiness checks. Exit code 0 iff every
suite passes.

Authoritative suites (current-state gates):
  * Sprint 0 bootstrap structure          tests/integration/test_bootstrap.sh
  * Sprint 2 database (migrations/RLS)     tests/integration/test_database.py
  * Sprint 3 ingestion (WF-001, JS)        tests/integration/WF-001_acceptance.test.js
  * Sprint 4 repository (JS)               tests/integration/repository_acceptance.test.js
  * Sprint 5 retrieval (py)                tests/integration/test_sprint5_retrieval.py
  * Sprint 6 reasoning (py)                tests/integration/test_sprint6_reasoning.py
  * Sprint 7 output (py)                   tests/integration/test_sprint7_output.py
  * Sprint 8 administration (py)           tests/integration/test_sprint8_administration.py
  * Sprint 9 benchmark/UAT (py)            tests/run_tests.py

Historical point-in-time snapshots (test_platform_foundation.sh,
test_sprint2_database.sh) are intentionally excluded — see their headers.

Usage: python tests/run_all.py [--verbose]
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (label, argv, success_substring-or-None-means-returncode-0)
SUITES = [
    ("Sprint 0 · bootstrap structure",
     ["bash", "tests/integration/test_bootstrap.sh"], "ACCEPTANCE: PASS"),
    ("Sprint 2 · database",
     ["python3", "tests/integration/test_database.py"], "0 failed"),
    ("Sprint 3 · WF-001 ingestion",
     ["node", "tests/integration/WF-001_acceptance.test.js"], "0 failed"),
    ("Sprint 4 · repository",
     ["node", "tests/integration/repository_acceptance.test.js"], "0 failed"),
    ("Sprint 5 · retrieval",
     ["python3", "tests/integration/test_sprint5_retrieval.py"], "tests passed"),
    ("Sprint 6 · reasoning",
     ["python3", "tests/integration/test_sprint6_reasoning.py"], None),
    ("Sprint 7 · output generation",
     ["python3", "tests/integration/test_sprint7_output.py"], None),
    ("Sprint 8 · administration",
     ["python3", "tests/integration/test_sprint8_administration.py"],
     "83/83 tests passing"),
    ("Sprint 9 · benchmark & UAT",
     ["python3", "tests/run_tests.py"], "50/50 passed"),
]


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def main() -> int:
    verbose = "--verbose" in sys.argv
    if not _have("node"):
        print("WARNING: node not found; JS suites will be skipped and the gate "
              "will FAIL (Node.js is a build dependency).")

    results = []
    for label, argv, needle in SUITES:
        if argv[0] == "node" and not _have("node"):
            results.append((label, False, "node missing"))
            continue
        proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        out = proc.stdout + proc.stderr
        if needle is None:
            ok = proc.returncode == 0
        else:
            ok = needle in out
        results.append((label, ok, ""))
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {label}")
        if verbose or not ok:
            tail = "\n".join(out.strip().splitlines()[-8:])
            print("        " + tail.replace("\n", "\n        "))

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("-" * 64)
    print(f"CRIE acceptance gate: {passed}/{total} suites passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
