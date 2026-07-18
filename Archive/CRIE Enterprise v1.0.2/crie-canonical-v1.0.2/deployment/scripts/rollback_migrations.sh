#!/usr/bin/env bash
# =============================================================================
# rollback_migrations.sh  (Sprint 10, S10-4 · §239)
# -----------------------------------------------------------------------------
# Runs the matching rollback scripts in DESCENDING order. Optionally stops at a
# target migration number (inclusive) so you can roll back only the additive
# tail (e.g. undo Sprint 9's 0027-0028 without touching the base schema).
#
#   # roll back everything:
#   DATABASE_URL=... bash deployment/scripts/rollback_migrations.sh
#
#   # roll back down to (and including) 0024:
#   DATABASE_URL=... bash deployment/scripts/rollback_migrations.sh 0024
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
RB_DIR="$ROOT/database/rollback"
STOP_AT="${1:-0001}"   # roll back down to this migration number, inclusive

: "${DATABASE_URL:?set DATABASE_URL}"

echo "== CRIE rollback :: reverse order, down to and including ${STOP_AT} =="
shopt -s nullglob
mapfile -t files < <(ls -1 "$RB_DIR"/0*_rollback.sql | sort -r)
for f in "${files[@]}"; do
  num="$(basename "$f" | grep -oE '^[0-9]{4}')"
  if [[ "$num" < "$STOP_AT" ]]; then
    break
  fi
  echo "  -> rolling back $(basename "$f")"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done
echo "== rollback complete =="
