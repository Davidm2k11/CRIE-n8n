#!/usr/bin/env bash
# [HISTORICAL — NON-GATING as of v1.0.0] This suite asserts the repository
# state at the END OF ITS OWN SPRINT (point-in-time snapshot: e.g. "no
# prompt bodies yet", "only UT-007 built", "exactly 23 migrations").
# Those conditions are intentionally no longer true in the completed
# canonical repository, so this snapshot is expected to report deltas and
# is retained for historical provenance only. It is NOT part of the v1.0.0
# production acceptance gate; the authoritative gate is tests/run_all.py.
# test_sprint2_database.sh — Sprint 2 acceptance test.
# DoD: Database fully operational; all migrations execute cleanly; acceptance
# tests pass (§150, §238). Live execution is an operator step; here we assert the
# migration set is complete, correct, reversible, config-driven, and that the
# startup checks validate the new user-adjustable DB configuration.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT" || exit 2
pass=0; fail=0
ok(){ printf '  ✓ %s\n' "$1"; pass=$((pass+1)); }
bad(){ printf '  ✗ %s\n' "$1"; fail=$((fail+1)); }

echo "== DB acceptance (§238, §150) =="
if python3 tests/integration/test_database.py >/tmp/db.txt 2>&1; then
  ok "DB acceptance: $(grep -c '✓' /tmp/db.txt) checks pass"
else bad "DB acceptance failed"; cat /tmp/db.txt; fi

echo "== Seed generates valid idempotent SQL from authored YAML (R-08) =="
if python3 scripts/setup/seed_configuration.py >/tmp/seed.sql 2>&1 && grep -q 'ON CONFLICT' /tmp/seed.sql; then
  ok "seed_configuration.py emits idempotent SQL ($(grep -c ';' /tmp/seed.sql) statements)"
else bad "seed generation failed"; fi

echo "== Vector index DDL is config-driven (§227) =="
if python3 scripts/setup/apply_vector_index.py | grep -q 'USING hnsw'; then
  ok "apply_vector_index.py emits index DDL from embedding.vectorIndex"
else bad "vector index generation failed"; fi

echo "== Startup Validation still PASS incl. new DB-config checks =="
python3 scripts/setup/validate_configuration.py --json >/tmp/health.json 2>/dev/null
if grep -q '"overall": "Healthy"' /tmp/health.json; then
  ok "Startup Validation Healthy (validates vector index, authority sources, categories)"
else bad "Startup Validation not Healthy"; fi

echo "== User-adjustable behavior is configurable without source edits =="
# Prove: changing a config value flows into the generated seed SQL.
if python3 - <<'PY'
import yaml, subprocess, sys
p="configuration/retrieval.yaml"; orig=open(p).read(); d=yaml.safe_load(orig)
d["retrieval"]["topK"]=25
open(p,"w").write(yaml.safe_dump(d,sort_keys=False))
out=subprocess.run(["python3","scripts/setup/seed_configuration.py"],capture_output=True,text=True).stdout
open(p,"w").write(orig)  # restore
sys.exit(0 if "'retrieval.topK'" in out and "'25'::jsonb" in out else 1)
PY
then ok "config change (topK) flows into seed with no source edits"; else bad "config not flowing to seed"; fi

echo "== No Sprint-3+ artifacts present =="
m=$(find workflows/master -name '*.json'|wc -l|tr -d ' ')
s=$(find workflows/shared -name '*.json'|wc -l|tr -d ' ')
b=$(find prompts -name 'system.md' -o -name 'user.md'|wc -l|tr -d ' ')
[ "$m" = 0 ] && ok "no master workflows (Sprint 3+ absent)" || bad "$m master workflows present"
[ "$s" = 0 ] && ok "no shared sub-workflows (Sprint 3+ absent)" || bad "$s shared workflows present"
[ "$b" = 0 ] && ok "no prompt bodies (Sprint 3+ absent)" || bad "$b prompt bodies present"

echo
echo "-------------------------------------------"
echo "Sprint 2 acceptance: $pass passed, $fail failed."
if [ "$fail" -eq 0 ]; then
  echo "RESULT: PASS — Database complete; migrations correct & reversible; config-driven; startup-validated."
  exit 0
else echo "RESULT: FAIL"; exit 1; fi
