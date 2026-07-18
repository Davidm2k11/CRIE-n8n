"""
CRIE Sprint 9 standalone test runner.

Executes the acceptance suite without an external pytest install (the build
environment is offline). Provides the minimal `pytest.approx` / `pytest.raises`
surface the suite uses, discovers every top-level `test_*` function, runs it,
and reports pass/fail counts. Exit code 0 iff all tests pass.

Usage: python tests/run_tests.py
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys
import traceback
import types


# --------------------------------------------------------------------------- #
# Minimal pytest shim
# --------------------------------------------------------------------------- #
class _Approx:
    def __init__(self, expected, rel=1e-6, abs_=1e-9):
        self.expected = expected
        self.rel = rel
        self.abs = abs_

    def __eq__(self, other):
        return math.isclose(other, self.expected, rel_tol=self.rel, abs_tol=self.abs)

    def __repr__(self):
        return f"approx({self.expected})"


class _Raises:
    def __init__(self, exc):
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            raise AssertionError(f"expected {self.exc.__name__} was not raised")
        return issubclass(exc_type, self.exc)


def _make_pytest_shim() -> types.ModuleType:
    mod = types.ModuleType("pytest")
    mod.approx = lambda expected, rel=1e-6, abs=1e-9: _Approx(expected, rel, abs)
    mod.raises = lambda exc: _Raises(exc)
    return mod


def main() -> int:
    # Install shim BEFORE importing the suite (suite does `import pytest`).
    sys.modules.setdefault("pytest", _make_pytest_shim())

    here = os.path.dirname(os.path.abspath(__file__))
    # Canonical layout: integration suites live under tests/integration/.
    suite_path = os.path.join(here, "integration", "test_sprint9_acceptance.py")

    spec = importlib.util.spec_from_file_location("test_sprint9_acceptance", suite_path)
    suite = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite)

    tests = sorted(
        (name, obj) for name, obj in vars(suite).items()
        if name.startswith("test_") and callable(obj)
    )

    passed, failed = 0, 0
    failures = []
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"PASS  {name}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            failures.append((name, exc, traceback.format_exc()))
            print(f"FAIL  {name}: {exc}")

    total = passed + failed
    print("-" * 60)
    print(f"Sprint 9 acceptance: {passed}/{total} passed")
    if failures:
        print("\nFailure detail:")
        for name, exc, tb in failures:
            print(f"\n### {name}\n{tb}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
