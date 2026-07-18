#!/usr/bin/env bash
# verify_bootstrap.sh — Sprint 0 verification
# Verifies the repository against the frozen v1.1 spec:
#   §619–633 folder hierarchy, §634 naming, §635 metadata,
#   §636 Bootstrap Checklist, §637 Acceptance Criteria.
# Exit 0 = bootstrap valid; non-zero = one or more checks failed.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 2

# --strict-bootstrap asserts the §637 point-in-time "no business logic yet"
# criterion (empty config, no SQL, no workflow JSON). This is only true at the
# end of Sprint 0; after Sprint 1 the structural checks remain valid but the
# emptiness checks no longer apply. Structural verification always runs.
STRICT_BOOTSTRAP=0
[ "${1:-}" = "--strict-bootstrap" ] && STRICT_BOOTSTRAP=1

pass=0; fail=0
ok()   { printf '  ✓ %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  ✗ %s\n' "$1"; fail=$((fail+1)); }

need_dir()  { if [ -d "$1" ]; then ok "dir  $1"; else bad "MISSING dir  $1"; fi; }
need_file() { if [ -f "$1" ]; then ok "file $1"; else bad "MISSING file $1"; fi; }

echo "== §619 Root folders =="
for d in .github configuration database deployment docs examples prompts \
         scripts tests workflows benchmark schemas assets; do need_dir "$d"; done

echo "== §635 Mandatory root metadata files =="
for f in README.md CHANGELOG.md VERSION LICENSE .gitignore .env.example; do need_file "$f"; done

echo "== §620 docs/ =="
for d in architecture implementation deployment operations api prompts \
         workflows benchmark governance troubleshooting; do need_dir "docs/$d"; done

echo "== §621 database/ =="
for d in migrations rollback seeds functions views policies indexes diagrams; do need_dir "database/$d"; done
need_file "database/README.md"

echo "== §622–625 workflows/ =="
for d in master shared utilities templates credentials documentation; do need_dir "workflows/$d"; done

echo "== §626 prompts/ =="
for d in knowledge compliance validation review templates examples schemas; do need_dir "prompts/$d"; done

echo "== §627 configuration YAML (10 files) =="
for f in providers repository retrieval reasoning monitoring feature_flags \
         logging storage security benchmark; do need_file "configuration/$f.yaml"; done

echo "== §628 tests/ =="
for d in unit integration regression benchmark uat fixtures datasets; do need_dir "tests/$d"; done

echo "== §629 examples/ =="
for d in documents rfps rfi compliance expected_outputs repository google_sheets; do need_dir "examples/$d"; done

echo "== §630 deployment/ =="
for d in docker docker-compose supabase n8n production development scripts; do need_dir "deployment/$d"; done

echo "== §631 benchmark/ =="
for d in knowledge retrieval reasoning proposal performance reports; do need_dir "benchmark/$d"; done

echo "== §632 schemas/ =="
for d in json yaml contracts validation; do need_dir "schemas/$d"; done

echo "== §633 scripts/ =="
for d in setup migration benchmark cleanup deployment repository; do need_dir "scripts/$d"; done

echo "== §635 VERSION is semantic (v0.1.0 baseline) =="
if grep -Eq '^v?[0-9]+\.[0-9]+\.[0-9]+$' VERSION; then ok "VERSION = $(cat VERSION)"; else bad "VERSION not semantic: $(cat VERSION)"; fi

echo "== §634 Folder naming is snake_case (no camelCase/spaces) =="
# §634 mandates snake_case folders, EXCEPT canonical identifier folders whose
# names are fixed IDs (§626 prompt-ID folders PR-XXX; workflow-ID folders
# WF-XXX / SW-XXX / UT-XXX). Those uppercase IDs are required by the spec and
# are not naming violations. Exclude them before flagging.
badnames="$(find . -type d -not -path './.git*' \
  | grep -E '[A-Z ]' \
  | grep -Ev '/(PR|WF|SW|UT)-[0-9]+(/|$)' \
  || true)"
if [ -z "$badnames" ]; then ok "all folders snake_case (canonical ID folders exempt)"; else bad "non-snake_case folders:"; echo "$badnames"; fi

if [ "$STRICT_BOOTSTRAP" = "1" ]; then
  echo "== §637 No business logic yet (config YAML empty; no SQL/JSON workflows) [strict] =="
  nonempty_cfg="$(find configuration -name '*.yaml' -size +0c || true)"
  if [ -z "$nonempty_cfg" ]; then ok "all configuration YAML empty"; else bad "non-empty config: $nonempty_cfg"; fi
  sqlcount=$(find database -name '*.sql' | wc -l | tr -d ' ')
  wfcount=$(find workflows -name '*.json' | wc -l | tr -d ' ')
  if [ "$sqlcount" = "0" ]; then ok "no .sql files"; else bad "$sqlcount .sql present"; fi
  if [ "$wfcount" = "0" ]; then ok "no workflow .json files"; else bad "$wfcount workflow .json present"; fi
else
  echo "== §637 emptiness checks skipped (post-Sprint-0; run with --strict-bootstrap to enforce) =="
fi

echo
echo "-------------------------------------------"
echo "Bootstrap verification: $pass passed, $fail failed."
if [ "$fail" -eq 0 ]; then
  echo "RESULT: PASS — Bootstrap Checklist (§636) & Acceptance Criteria (§637) satisfied."
  exit 0
else
  echo "RESULT: FAIL — fix the items above."
  exit 1
fi
