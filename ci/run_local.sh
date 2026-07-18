#!/usr/bin/env bash
# ci/run_local.sh — run the CRIE CI regression guards locally (Linux/macOS/Git Bash).
#
# Runs the SAME checks as .github/workflows/ci.yml:
#   1. Workflow static validation (ACTIVE/shipped set)
#   2. Migration replay: bootstrap roles -> apply chain twice (idempotency) -> verify
#
# Prerequisites:
#   - python3 on PATH
#   - psql on PATH
#   - A reachable PostgreSQL 16 with pgvector available. Easiest:
#       docker run --rm -d --name crie-ci -e POSTGRES_PASSWORD=postgres \
#         -e POSTGRES_DB=crie_ci -p 5432:5432 pgvector/pgvector:pg16
#
# Usage (from repo root):
#   PGURL=postgres://postgres:postgres@localhost:5432/crie_ci bash ci/run_local.sh
#
# The replay DB should be empty on first run; re-running is safe (the chain is
# idempotent — that is exactly what pass 2 proves).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PGURL="${PGURL:-postgres://postgres:postgres@localhost:5432/crie_ci}"

# The active workflow set is configuration-driven: with no path args the validator
# reads ci/active_workflows.txt (the single source of truth for what CI validates).
echo "== 1/3  Workflow static validation =="
python3 "$ROOT/ci/validate_workflows.py"

echo "== 2/3  Migration replay (bootstrap + chain x2) =="
psql "$PGURL" -v ON_ERROR_STOP=1 -f "$ROOT/ci/replay/bootstrap.sql"
for pass in 1 2; do
    echo "-- apply pass $pass --"
    for f in $(ls "$ROOT"/migrations/*.sql | sort); do
        psql "$PGURL" -v ON_ERROR_STOP=1 -f "$f" >/dev/null
    done
done

echo "== 3/3  Post-replay verification =="
psql "$PGURL" -v ON_ERROR_STOP=1 -f "$ROOT/ci/replay/verify.sql"

echo ""
echo "ALL GUARDS PASSED"
