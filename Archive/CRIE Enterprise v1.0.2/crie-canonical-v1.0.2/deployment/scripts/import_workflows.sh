#!/usr/bin/env bash
# =============================================================================
# import_workflows.sh  (Sprint 10, S10-4 · §623/§634)
# -----------------------------------------------------------------------------
# Imports every CRIE workflow JSON into an n8n instance using the n8n CLI. Run
# inside the n8n-main container (or any host with the n8n CLI and the same
# N8N_ENCRYPTION_KEY / DB env as the target instance).
#
#   docker compose -f deployment/docker-compose/docker-compose.yml \
#       exec n8n-main sh -c \
#       "for f in /workflows/master/*.json /workflows/utilities/*.json /workflows/shared/*.json; do n8n import:workflow --input=\"\$f\"; done"
#
# Or on a host with n8n installed:
#   bash deployment/scripts/import_workflows.sh /path/to/repo/workflows
#
# Workflow IDs never change after publication (§634); re-import updates in place.
# =============================================================================
set -euo pipefail

WF_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)/workflows}"

if ! command -v n8n >/dev/null 2>&1; then
  echo "n8n CLI not found on PATH. Run this inside the n8n container, e.g.:" >&2
  echo "  docker compose ... exec n8n-main sh -c '...'  (see header)" >&2
  exit 2
fi

import_dir() {
  local dir="$1"
  [ -d "$dir" ] || return 0
  for f in "$dir"/*.json; do
    [ -e "$f" ] || continue
    echo "  importing $(basename "$f")"
    n8n import:workflow --input="$f"
  done
}

echo "== importing CRIE workflows from $WF_ROOT =="
import_dir "$WF_ROOT/master"
import_dir "$WF_ROOT/utilities"
import_dir "$WF_ROOT/shared"
echo "== workflow import complete =="
echo "NOTE: activate the Startup Validation (UT-007) and scheduled workflows in"
echo "      the n8n UI, and bind provider credentials (never stored in JSON)."
