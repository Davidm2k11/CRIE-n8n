#!/usr/bin/env bash
# =============================================================================
# apply_migrations.sh  (Sprint 10, S10-4 · §217/§239/§630)
# -----------------------------------------------------------------------------
# Applies every CRIE migration in ascending numeric order and STOPS on the first
# failure (§217). Idempotent to the extent each migration is (the 0001-0028 set
# uses IF NOT EXISTS / CREATE OR REPLACE throughout). Reversible via
# rollback_migrations.sh.
#
# Requires: psql on PATH, and a DATABASE_URL (or SUPABASE_URL + credentials).
#
#   DATABASE_URL="postgresql://crie:pass@localhost:5432/crie" \
#       bash deployment/scripts/apply_migrations.sh
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
MIG_DIR="$ROOT/database/migrations"

: "${DATABASE_URL:?set DATABASE_URL (e.g. postgresql://user:pass@host:5432/crie)}"

echo "== CRIE migrations :: applying $MIG_DIR in order (stop on first failure) =="
shopt -s nullglob
applied=0
for f in "$MIG_DIR"/0*.sql; do
  echo "  -> applying $(basename "$f")"
  if ! psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"; then
    echo "  STOP: $(basename "$f") failed — aborting (§217)" >&2
    exit 1
  fi
  applied=$((applied+1))
done

echo "== applied $applied migration(s) successfully =="
echo "== next: seed configuration (R-08):  bash deployment/scripts/seed_config.sh =="
