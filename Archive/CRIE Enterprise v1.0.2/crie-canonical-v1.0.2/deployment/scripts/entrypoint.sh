#!/usr/bin/env bash
# =============================================================================
# entrypoint.sh  (Sprint 10, S10-4 · §630 scripts/)
# -----------------------------------------------------------------------------
# Single ops entrypoint for the CRIE tooling image. Dispatches to the individual
# deployment scripts. All operations are idempotent (§633).
#
#   docker run --rm --env-file .env crie-tools:1.0.0 \
#       bash deployment/scripts/entrypoint.sh <command>
#
# Commands:
#   migrate        apply migrations in order (§217)
#   rollback [N]   roll back to migration N (default: all)
#   seed           validate config + sync YAML -> config tables (R-08/§327)
#   validate       run R-14 startup validation only (§327)
#   smoke          run post-deploy smoke checks (§200)
#   gate           run the full acceptance gate (tests/run_all.py)
#   benchmark      run the benchmark harness (Sprint 9)
#   help           show this help
# =============================================================================
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cmd="${1:-help}"; shift || true

case "$cmd" in
  migrate)    exec bash "$ROOT/deployment/scripts/apply_migrations.sh" "$@" ;;
  rollback)   exec bash "$ROOT/deployment/scripts/rollback_migrations.sh" "$@" ;;
  seed)       exec bash "$ROOT/deployment/scripts/seed_config.sh" "$@" ;;
  validate)   exec python3 "$ROOT/scripts/setup/validate_configuration.py" "$@" ;;
  smoke)      exec bash "$ROOT/deployment/scripts/smoke_test.sh" "$@" ;;
  gate)       exec python3 "$ROOT/tests/run_all.py" "$@" ;;
  benchmark)  exec python3 "$ROOT/scripts/benchmark/run_benchmark.py" "$@" ;;
  help|--help|-h)
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    echo "unknown command: $cmd" >&2
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2 ;;
esac
