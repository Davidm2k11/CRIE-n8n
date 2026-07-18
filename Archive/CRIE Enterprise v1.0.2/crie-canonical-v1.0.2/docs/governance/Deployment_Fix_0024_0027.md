# Deployment Fix Report — Clean Sequential Migration Apply (v1.0.2)

_Trigger: the v1.0.1 hotfix repaired migration 0024's view bodies but was
validated against a catalog that assumed objects from later migrations (0026,
0027) already existed. The real deploy applies migrations 0001→0028 in strict
numeric order (`deployment/scripts/apply_migrations.sh`, `psql -v ON_ERROR_STOP=1`),
so 0024 still failed, and migrations 0025/0026 carried the same class of drift._
_Scope: minimal deployment fixes only. No redesign; frozen migrations 0001–0023
untouched. Result: v1.0.2._

## 1. Method

Because the build environment has no live PostgreSQL, correctness was verified by
a **sequential catalog bind-check**: the schema catalog is built migration by
migration in apply order (0001, 0002, …), and every `FROM`/`JOIN` target and every
aliased column reference in each view migration is resolved against the catalog
**as it exists at that migration's position** — not against the final schema. This
is the check the v1.0.1 fix omitted, and it is what a live `psql` apply enforces.

## 2. Root causes (three, all the same defect class)

### 2.1 `0012`/`0027` `monitoring.benchmark_results` name collision (primary)
Migration `0012` creates a placeholder `monitoring.benchmark_results`
(`dataset, metric, value, target, created_at`) with **no readers anywhere** in the
codebase. Migration `0027` (Sprint 9) intends the real table
(`run_id, benchmark, metric, metric_value, target_value, higher_is_better, passed,
spec_ref, recorded_at, …`). Because `0027` uses `CREATE TABLE IF NOT EXISTS`, on a
clean sequential apply the placeholder wins and `0027` is a **silent no-op** — so
the 0027 columns never exist. Every 0027-shape consumer then fails:
`admin.vw_benchmark_dashboard` (0024), the `admin.v_benchmark_*` views (0028), and
the benchmark INSERTs in `scripts/benchmark/run_benchmark.py` / `evaluate.py`.

### 2.2 `0024` forward dependencies
`admin.vw_main_dashboard.open_alerts` selected from `monitoring.alerts`, created by
`0026` (later). `admin.vw_benchmark_dashboard` selected from the `0027`-shape
`monitoring.benchmark_results` (later). Neither exists at 0024's apply position →
`CREATE VIEW` fails (views bind immediately).

### 2.3 `0025` phantom schema (same class the v1.0.1 audit found in 0024)
- `admin.vw_prompt_registry_dashboard` referenced `configuration.prompt_registry.status`,
  `.owner`, `.benchmark_status` (real columns: `prompt_id, version, name, category,
  latest, updated_at, id`) and `monitoring.ai_requests.prompt_id / latency_ms /
  confidence` (real: `latency`, no `prompt_id`, no `confidence`).
- `admin.vw_configuration_dashboard` referenced four tables **no migration creates**:
  `configuration.platform_config`, `.provider_config`, `.feature_flags`,
  `.secrets_registry`.

## 3. The minimal fixes (bodies only; every view name + output-column contract preserved)

| Migration | Change |
|---|---|
| **0027** | Added a guarded reconciliation block before the real `CREATE TABLE`: if `monitoring.benchmark_results` exists **without** the `metric_value` column (i.e. only the empty 0012 placeholder) **and holds no rows**, drop it; otherwise leave it. This makes 0027 the sole authoritative definition while leaving frozen migrations 0001–0023 untouched. Refuses to drop if real data is present. |
| **0024** | `open_alerts` → typed `0::bigint` placeholder (live count served by 0026's `admin.vw_alert_center`). `vw_benchmark_dashboard` → empty placeholder preserving its 5-column contract (live data served by 0028's `admin.v_benchmark_*`). |
| **0025** | `vw_prompt_registry_dashboard` → real `prompt_registry` columns + typed NULL/0 placeholders for the non-existent ones; dropped the invalid `ai_requests` join. `vw_configuration_dashboard` → repointed to the real `configuration.configuration` KV table and `configuration.providers`; feature-flags and secrets exposed as typed placeholders (secrets remain presence-only; no secret value is ever selected). |
| **0026** | `vw_health_center` → `hc.service`→`hc.component`, `hc.status`→`hc.state` (both aliased back to the original output names), `hc.latency`→typed NULL `latency_ms`. |
| **tests** | `tests/integration/test_sprint8_administration.py`: the secrets check asserted the literal token `is_present` (from the buggy phantom column); updated to assert the real presence-only output columns while still verifying no secret value is selected. |

**No object kind, view name, or output-column contract changed.** No table or
column invented (that would be a redesign). Rollbacks unchanged and still correct.
Migrations 0001–0023 unchanged (additive-only, R-15).

## 4. Verification (build environment)

- **Sequential catalog bind-check:** every `FROM`/`JOIN` target and every aliased
  column across migrations 0001–0028 resolves at its own apply position. Zero
  genuine misses (remaining matches are comment filenames and `information_schema`
  system catalogs).
- **Acceptance gate:** `python3 tests/run_all.py` → **9/9 suites, 265 tests**.
- **R-14 startup validation:** `python3 scripts/setup/validate_configuration.py`
  → **Healthy**.
- SQL parens balanced; `BEGIN`/`COMMIT` intact in every edited migration.

## 5. Still requires live PostgreSQL (unchanged from the handover §4)

The bind-check is static. The confirming test remains **deployment step 2**: run
`DATABASE_URL=… bash deployment/scripts/apply_migrations.sh` against the target DB
and confirm 0001–0028 all apply with no error. The recommended permanent guard
(handover §11 MEDIUM) — a CI job that spins up ephemeral PostgreSQL, applies all
migrations, and `SELECT`s one row from each `admin.vw_*` / `admin.v_*` view — would
catch this entire defect class automatically; it is noted but not added here
(out of the minimal-fix scope).
