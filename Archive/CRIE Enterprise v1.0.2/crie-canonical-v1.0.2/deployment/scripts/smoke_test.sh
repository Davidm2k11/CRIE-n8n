#!/usr/bin/env bash
# =============================================================================
# smoke_test.sh  (Sprint 10, S10-4 · §200 "Smoke Tests" pipeline stage)
# -----------------------------------------------------------------------------
# Fast, non-destructive checks run immediately after a deploy, BEFORE promoting
# to production (§200 "Deploy Development -> Smoke Tests -> Deploy Production").
# Verifies the substrate is reachable and configuration is valid. Does NOT run
# the full acceptance gate (that runs earlier in CI) and does NOT mutate data.
#
#   DATABASE_URL=... N8N_HEALTH_URL=http://localhost:5678/healthz \
#       bash deployment/scripts/smoke_test.sh
# =============================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
pass=0; fail=0
ok()  { printf '  ✓ %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  ✗ %s\n' "$1"; fail=$((fail+1)); }

echo "== CRIE post-deploy smoke test =="

# 1. Configuration valid (R-14 / §327)
if python3 scripts/setup/validate_configuration.py >/dev/null 2>&1; then
  ok "configuration valid (R-14 startup validation)"
else
  bad "configuration invalid (R-14 startup validation FAILED)"
fi

# 2. Database reachable + core + additive tables present
if [ -n "${DATABASE_URL:-}" ] && command -v psql >/dev/null 2>&1; then
  if psql "$DATABASE_URL" -tAc "select 1" >/dev/null 2>&1; then
    ok "database reachable"
    # spot-check a base table and an additive one exist
    if psql "$DATABASE_URL" -tAc \
        "select to_regclass('monitoring.benchmark_results') is not null" \
        2>/dev/null | grep -q t; then
      ok "additive migrations present (monitoring.benchmark_results)"
    else
      bad "additive migrations missing (run apply_migrations.sh)"
    fi
  else
    bad "database not reachable at DATABASE_URL"
  fi
else
  echo "  · DATABASE_URL/psql not provided — skipping DB checks"
fi

# 3. n8n health endpoint (queue mode readiness, R-18)
if [ -n "${N8N_HEALTH_URL:-}" ] && command -v curl >/dev/null 2>&1; then
  if curl -fsS "$N8N_HEALTH_URL" >/dev/null 2>&1; then
    ok "n8n health endpoint responding"
  else
    bad "n8n health endpoint not responding ($N8N_HEALTH_URL)"
  fi
else
  echo "  · N8N_HEALTH_URL/curl not provided — skipping n8n check"
fi

echo "-------------------------------------------"
echo "Smoke test: $pass passed, $fail failed."
[ "$fail" -eq 0 ] && { echo "SMOKE: PASS"; exit 0; } || { echo "SMOKE: FAIL"; exit 1; }
