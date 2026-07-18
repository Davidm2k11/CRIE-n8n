#!/usr/bin/env bash
# [HISTORICAL — NON-GATING as of v1.0.0] This suite asserts the repository
# state at the END OF ITS OWN SPRINT (point-in-time snapshot: e.g. "no
# prompt bodies yet", "only UT-007 built", "exactly 23 migrations").
# Those conditions are intentionally no longer true in the completed
# canonical repository, so this snapshot is expected to report deltas and
# is retained for historical provenance only. It is NOT part of the v1.0.0
# production acceptance gate; the authoritative gate is tests/run_all.py.
# test_platform_foundation.sh — Sprint 1 acceptance test.
# Sprint 1 DoD (R-14): Startup Validation workflow passes (config + secrets +
# providers valid) and platform health = Healthy. This harness asserts the DoD
# and the Platform-Foundation acceptance criteria (§20, §328), and confirms no
# future-sprint artifacts leaked into Sprint 1.

set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 2

pass=0; fail=0
ok()  { printf '  ✓ %s\n' "$1"; pass=$((pass+1)); }
bad() { printf '  ✗ %s\n' "$1"; fail=$((fail+1)); }

echo "== Configuration YAML parses (§627 authored source of truth) =="
if python3 - <<'PY'
import yaml, glob, sys
bad=[]
for f in sorted(glob.glob("configuration/*.yaml")):
    try: yaml.safe_load(open(f))
    except Exception as e: bad.append((f,str(e)))
if bad:
    [print("INVALID",f,e) for f,e in bad]; sys.exit(1)
sys.exit(0)
PY
then ok "all 10 configuration YAML files valid"; else bad "invalid configuration YAML"; fi

echo "== Prompt & Workflow registries parse; canonical catalogs correct =="
python3 - <<'PY'
import yaml, sys
p=yaml.safe_load(open("prompts/registry.yaml"))
ids=[x["id"] for x in p["prompts"]]
assert ids==[f"PR-00{i}" for i in range(1,9)], ids            # R-04 eight-prompt set
assert all(x["latestVersion"] is None for x in p["prompts"])  # no bodies yet (S1-3)
w=yaml.safe_load(open("workflows/registry.yaml"))
assert len(w["master"])==5                                     # R-02 five masters
assert len(w["shared"])==28                                    # R-01 Module 13 catalog
built=[x["id"] for s in ("master","shared","utilities") for x in w[s] if x["status"]=="built"]
assert built==["UT-007"], built                                # only startup validation built
print("registries OK")
PY
if [ $? -eq 0 ]; then ok "prompt registry = PR-001..PR-008 (no bodies); workflow registry = 5 master + 28 shared; only UT-007 built"; else bad "registry contents wrong"; fi

echo "== Canonical JSON contracts are well-formed =="
if python3 - <<'PY'
import json, glob, sys
bad=[]
for f in glob.glob("schemas/contracts/*.json") + glob.glob("schemas/yaml/*.json"):
    try:
        d=json.load(open(f))
        assert "$schema" in d and ("type" in d or "$defs" in d), f
    except Exception as e:
        bad.append((f,str(e)))
if bad:
    [print("BAD",f,e) for f,e in bad]; sys.exit(1)
sys.exit(0)
PY
then ok "log, telemetry, health, adapter_error, workflow_error, execution_summary, config schemas valid"; else bad "malformed contract schema"; fi

echo "== Startup Validation workflow is valid n8n JSON =="
if python3 - <<'PY'
import json, sys
d=json.load(open("workflows/utilities/UT-007_Startup_Validation.json"))
assert d["name"]=="UT-007_Startup_Validation"
assert len(d["nodes"])>=4 and "connections" in d
sys.exit(0)
PY
then ok "UT-007_Startup_Validation.json is valid n8n workflow JSON"; else bad "invalid workflow JSON"; fi

echo "== R-14 EXIT GATE: Startup Validation passes; health = Healthy =="
OUT="$(python3 scripts/setup/validate_configuration.py --json)"
rc=$?
if [ $rc -eq 0 ] && echo "$OUT" | grep -q '"overall": "Healthy"'; then
  ok "Startup Validation PASS — platform health = Healthy"
else
  bad "Startup Validation did not pass / health not Healthy"; echo "$OUT"
fi

echo "== §312 feature flags all default false =="
if python3 - <<'PY'
import yaml,sys
f=yaml.safe_load(open("configuration/feature_flags.yaml"))["featureFlags"]
sys.exit(0 if all(v is False for v in f.values()) else 1)
PY
then ok "all feature flags default false"; else bad "a feature flag is not false"; fi

echo "== Principle 7 / §313: no secret VALUES in config or workflows =="
# env placeholders (\${...}) are allowed; real-looking keys are not.
if grep -RInE 'sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN' configuration workflows prompts schemas 2>/dev/null; then
  bad "possible secret material found"
else ok "no secret values embedded (only \${ENV} placeholders)"; fi

echo "== No Sprint-3+ artifacts present (checked here; Sprint 2 DB is now allowed) =="
masters=$(find workflows/master -name '*.json' | wc -l | tr -d ' ')  # Sprint 3+
shared=$(find workflows/shared -name '*.json' | wc -l | tr -d ' ')   # Sprint 3+
bodies=$(find prompts -name 'system.md' -o -name 'user.md' | wc -l | tr -d ' ') # Sprint 3+
[ "$masters" = 0 ] && ok "no master workflow JSON (Sprint 3+ absent)" || bad "$masters master workflow(s) present"
[ "$shared" = 0 ]  && ok "no shared sub-workflow JSON (Sprint 3+ absent)" || bad "$shared shared workflow(s) present"
[ "$bodies" = 0 ]  && ok "no prompt bodies (Sprint 3+ absent)"       || bad "$bodies prompt body file(s) present"

echo
echo "-------------------------------------------"
echo "Sprint 1 acceptance: $pass passed, $fail failed."
if [ "$fail" -eq 0 ]; then
  echo "RESULT: PASS — Platform Foundation complete; Startup Validation passes; health Healthy (R-14)."
  exit 0
else
  echo "RESULT: FAIL"; exit 1
fi
