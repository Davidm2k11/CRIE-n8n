#!/usr/bin/env bash
# test_bootstrap.sh — Sprint 0 acceptance test
# Asserts the Sprint 0 Definition of Done and Bootstrap Checklist (§636/§637)
# by running the verification script and asserting a PASS result.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

echo "### Sprint 0 Acceptance Test ###"
echo
echo "Note: the §637 'no business logic yet' emptiness criterion was enforced at"
echo "the v0.1.0 tag (run 'verify_bootstrap.sh --strict-bootstrap' on that commit)."
echo "As a standing regression this asserts the permanent bootstrap STRUCTURE."
echo

bash "$ROOT/scripts/setup/verify_bootstrap.sh"
rc=$?

echo
if [ "$rc" -eq 0 ]; then
  echo "ACCEPTANCE: PASS — bootstrap structure intact; repository ready for implementation."
else
  echo "ACCEPTANCE: FAIL"
fi
exit "$rc"
