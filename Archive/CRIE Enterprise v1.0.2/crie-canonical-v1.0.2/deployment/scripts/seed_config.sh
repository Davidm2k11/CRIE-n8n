#!/usr/bin/env bash
# =============================================================================
# seed_config.sh  (Sprint 10, S10-4 · R-08 / §236 / §327)
# -----------------------------------------------------------------------------
# Syncs the authored YAML sources of truth into the configuration.* runtime
# cache tables. This is the ONLY supported way configuration enters the
# database — values are never authored directly in the tables (§627). Re-run
# after editing any configuration/*.yaml; the emitted SQL is idempotent
# (ON CONFLICT ... DO UPDATE).
#
# Also runs the R-14 startup validation first and STOPS if configuration is
# invalid (§327 "missing mandatory configuration SHALL block execution").
#
#   DATABASE_URL=... bash deployment/scripts/seed_config.sh
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== R-14 startup validation (§327) =="
if ! python3 scripts/setup/validate_configuration.py; then
  echo "STOP: configuration invalid — refusing to seed (§327)" >&2
  exit 1
fi

echo "== emitting + applying configuration sync SQL (R-08) =="
if [ -n "${DATABASE_URL:-}" ]; then
  # --apply executes directly when a psycopg driver is present; otherwise it
  # emits SQL which we pipe to psql.
  if ! python3 scripts/setup/seed_configuration.py --apply 2>/dev/null; then
    python3 scripts/setup/seed_configuration.py | psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q
  fi
  echo "== configuration synced =="
else
  echo "DATABASE_URL not set — emitting SQL to stdout only"
  python3 scripts/setup/seed_configuration.py
fi
