# Changelog

All notable changes to CRIE are recorded here. Versions follow the sprint
roadmap (R-07, §639–655). Each entry corresponds to a tagged sprint release.

## [1.0.2] — Deployment hotfix 2 · clean sequential migration apply

Continuation of the v1.0.1 deployment hardening. The v1.0.1 fix repaired 0024's
view bodies but validated them against a catalog that assumed objects from
migrations 0026/0027 already existed. In the real deploy (`apply_migrations.sh`
applies 0001→0028 in strict numeric order with `ON_ERROR_STOP=1`), those objects
do not exist at 0024's position, so 0024 still failed — and two further migrations
(0025, 0026) carried the same phantom-schema drift. This release makes the full
0001–0028 set apply cleanly in order. Frozen migrations 0001–0023 remain
untouched; all changes are confined to additive migrations 0024–0027 (view/table
bodies only) plus one text-based test-fixture token.

### Fixed
- **0012/0027 `monitoring.benchmark_results` collision (root cause of the
  benchmark-layer failures).** Migration 0012 shipped an unused placeholder table
  of the same name with an incompatible shape and no readers; its `IF NOT EXISTS`
  presence silently suppressed the real Sprint 9 (0027) definition, breaking every
  0027-shape consumer (0024/0028 views, `run_benchmark.py`, `evaluate.py`).
  Reconciled inside additive migration **0027** with a guarded drop-and-recreate
  (drops only the empty legacy placeholder; refuses if real data is present),
  leaving 0001–0023 frozen. 0027 is now the sole authoritative definition.
- **0024 forward dependencies.** `vw_main_dashboard.open_alerts` referenced
  `monitoring.alerts` (created later in 0026) → exposed as typed `0` placeholder
  (live count is served by 0026's `admin.vw_alert_center`).
  `vw_benchmark_dashboard` referenced the 0027-shape `monitoring.benchmark_results`
  (created later in 0027) → reduced to an empty placeholder preserving its exact
  output-column contract (live benchmark data is served by 0028's
  `admin.v_benchmark_*` views).
- **0025 phantom schema (same class as the v1.0.1 0024 audit).**
  `vw_prompt_registry_dashboard` referenced non-existent
  `configuration.prompt_registry.status/owner/benchmark_status` and non-existent
  `monitoring.ai_requests.prompt_id/latency_ms/confidence` → repointed to real
  columns or typed NULL/0 placeholders. `vw_configuration_dashboard` referenced
  four tables no migration creates (`configuration.platform_config/provider_config/
  feature_flags/secrets_registry`) → repointed to the real `configuration.configuration`
  KV table and `configuration.providers`, with feature-flags/secrets exposed as
  typed placeholders (secrets still presence-only; no secret value is ever selected).
- **0026 phantom `health_checks` columns.** `vw_health_center` referenced
  `hc.service/status/latency` → repointed to real `component`/`state` (aliased back
  to preserve the output-column contract) with `latency_ms` as a typed NULL.

### Preserved
- No object kind, view name, or output-column contract changed; BI bindings (R-17)
  and the Sprint 8/9 acceptance suites are unaffected. No table or column invented.
  Migrations 0001–0023 unchanged (additive-only invariant, R-15). Rollbacks
  unchanged and still correct. Acceptance gate 9/9 (265 tests) and R-14 startup
  validation Healthy after the fix.

## [1.0.1] — Deployment hotfix · migration 0024

Deployment-blocking fix. Migration `0024_admin_dashboard_views.sql` (Sprint 8)
failed to apply against the frozen schema with
`ERROR: relation "repository.repository_health" does not exist`. Audit found
that 0024's view bodies were authored against a richer schema than migrations
0001–0023/0026/0027 actually create: **7 non-existent objects** (
`repository.repository_health` [which is a function/`vw_repository_health` view,
not a selectable table], `repository.review_queue`, `repository.requirements`,
`repository.proposals`, `monitoring.telemetry`, `configuration.reasoning_config`,
`configuration.benchmark_targets`) and **~9 non-existent columns** (
`health_checks.status/service/latency`, `ai_requests.confidence/latency_ms/success`,
`workflow_logs.created_at` + phantom name/version/payload/cost columns,
`documents.lifecycle_state`, `knowledge_units.language`, `benchmark_results.value/run_at`).

### Fixed
- Rewrote **only the SELECT bodies** of the 11 `admin.vw_*` views in 0024 so
  every reference resolves against the real frozen schema:
  `repository.repository_health` → `repository.vw_repository_health` with
  `.status`→`.state`; `health_checks.status`→`state`, `.service`→`component`;
  `ai_requests.latency_ms`→`latency`; `workflow_logs.created_at`→`timestamp`;
  `documents.lifecycle_state`→`documents.status` (certified count sourced from
  `knowledge_units.lifecycle_state`, where that column actually lives, added by
  0018); `benchmark_results` uses its own `metric_value`/`target_value`/
  `recorded_at`. References with **no v1 data source** (health score, review
  queue, requirements/proposals per-unit cost, telemetry latencies, AI success
  rate, workflow names/payloads) return a typed `NULL`/`0` placeholder.
- **No object kind, view name, or output-column contract changed** — every view
  keeps its exact name and column list, so BI bindings (R-17) and the Sprint 8/9
  acceptance suites are unaffected. No table or column was invented (that would
  be a redesign). No other migration, rollback, workflow, prompt, config, or
  contract touched. `0024` remains additive and read-only.

### Correct-fix note
The right fix for the reported line is `repository.vw_repository_health` (the
view; the identically-named function is not selectable with `FROM`), **and** its
column is `state`, not `status`; there is no `health_score` column in SQL (the
numeric score is computed in the repository health-statistics / BI layer, R-17),
so it is exposed as `NULL`. No additional object "should have existed" under the
frozen v1 architecture — the other referenced objects are out-of-scope future
features (§21), not omissions from Sprint 8's frozen deliverable.

### Verified
- Static column-bind check of all references against the real catalog: clean.
- Acceptance gate **9/9 (265 tests)**; Sprint 8 suite **83/83**; startup
  validation **Healthy**.

## [1.0.0] — Sprint 10 · Production Hardening

Final release. Prepares production deployment: adds the deployment/operations
layer and the §204/§407 documentation set, and fixes the repository-audit
findings that do not change the frozen architecture or feature set. Implements
**only** Sprint 10 scope. No migration, workflow, prompt, contract, or config
**value** was altered; benchmark numeric targets unchanged (§196).

### Added
- **Deployment layer (S10-4/5/6, §200/§325/§630):** `deployment/docker/`
  (Dockerfile + pinned requirements), `deployment/docker-compose/` reference
  stack (PostgreSQL+pgvector, Redis, n8n main+worker in **queue mode**, R-18),
  `production/` and `development/` compose overrides, `supabase/init/`
  bootstrap, `n8n/` env reference, and idempotent `scripts/`
  (`apply_migrations`, `rollback_migrations`, `seed_config`, `import_workflows`,
  `smoke_test`, `entrypoint`).
- **CI/CD (S10-4, §200):** `.github/workflows/ci.yml` mirroring the §200
  pipeline (Static → Workflow → Migration → Unit → Integration → Benchmark →
  Deploy Dev → Deploy Prod); stops on first failure; production deploy gated on
  a protected environment (§406 sign-offs).
- **Documentation (S10-1/5/6/8, §204/§407):** Deployment Guide, Operations
  Guide, Backup & Recovery Guide, API Guide, and the governance reports
  — Repository Audit Report, Security Review, Production Readiness Report — plus
  the Sprint 10 manifest.
- **Test tooling:** `tests/run_all.py` (unified acceptance gate, 9 suites /
  265 tests, used by CI and the §406/§616 checks); `tests/_pathsetup.py`
  (reconstructs the `retrieval`/`reasoning`/`output_generation` packages from
  the canonical flat modules — regenerates no logic).

### Fixed (audit; behavior-preserving, no architecture/feature change)
- Repository layer was **non-importable** in the canonical layout:
  `repository_api.js`/`repository_writer.js` required pre-integration filenames;
  corrected to canonical `repository_*` names.
- Acceptance suites were **non-runnable** in the canonical layout: corrected
  stale module/config/dataset/contract/example paths across the Sprint 5/6/7/8/9
  and JS suites and the Sprint 9 runner.
- **R-14 startup validation reported `Critical` against valid config**:
  `validate_configuration.py` now namespaces the unwrapped `retrieval.yaml` by
  filename stem and root-merges `providers.yaml`/`authority.yaml`; result
  `Healthy`. No config file mutated.
- **§634 folder-name check** wrongly flagged the spec-mandated `PR-00X`
  identifier folders; exempted canonical ID folders.
- `test_database.py` expected exactly 23 migrations; updated to the canonical
  additive set 0001–0028.
- Annotated `test_platform_foundation.sh` / `test_sprint2_database.sh` as
  historical point-in-time snapshots (non-gating).

### Packaging / security
- Removed the self-nested `crie-canonical-v0_10_0_tar.gz` from the tree;
  `.gitignore` now excludes release bundles. `.env.example` remains value-free.

### Status
- Acceptance gate **9/9 (265 tests)**; startup validation **Healthy**; benchmark
  harness clean. §406 gate **Met** except the deployment-side operational
  sign-offs (UAT, backup/recovery drills, live monitoring), reported **Pending**.
- `VERSION` → **1.0.0**. Tag `v1.0.0` applied in the canonical repository.

## [0.10.0] — Sprint 9 · Benchmarking & UAT

Validation framework per §194–199 and §390–406. Additive only; no feature
added, no architecture changed, benchmark numeric targets unchanged from spec.

### Added
- **Migration `0027_benchmark_persistence.sql`** (+ rollback): materializes
  `monitoring.benchmark_results` and `monitoring.latency_history` — tables the
  spec names (§130/§3953, §7086, §399) but v1.0 left without columns. Additive
  per §239.1/R-15.
- **Migration `0028_benchmark_views.sql`** (+ rollback): read-only `admin.*`
  views — `v_benchmark_latest_run`, `v_benchmark_target_summary`,
  `v_latency_latest_run`, `v_acceptance_criteria_matrix` (§405),
  `v_production_readiness_gate` (§406); and
  `monitoring.module_operational_validation` for operationally-validated
  modules. BI-agnostic (R-17): views consumed identically by Metabase / Power
  BI / Grafana.
- **Benchmark harness** (`benchmark/harness/`): real metric computations
  (§394–400), config loader with startup validation (R-08, §327/§157),
  evaluator, runner, and an in-memory adapter double.
- **Labeled benchmark dataset** (§392/§393): all 8 document categories × 4
  difficulty tiers, all 10 requirement types.
- **Test harnesses**: load (§401), failure/deterministic-recovery (§402),
  security (§403); UAT scripts for all 4 roles (§404).
- **Config** `config/benchmark.config.yaml` (R-08): frozen §196/§197/§394–400
  targets and §392/§393/§401–404 taxonomies — transcribed verbatim.
- **Benchmark Report** (`reports/BENCHMARK_REPORT.md`): Sprint 9 exit-gate
  deliverable.
- **Sprint 9 acceptance suite**: 50 tests, all passing, runnable offline via
  `tests/run_tests.py`.

### Notes
- Administration (§405) is validated operationally (§199/§390) because §400
  Cost is reported, not numerically gated; no numeric target was fabricated.
- §406 operational sign-offs (defect review, live UAT, backup/recovery drills,
  live monitoring) reported as *Pending deployment verification*, not passed;
  verified at Sprint 10 / deployment.

## [0.9.0] — Sprint 8 · Administration (WF-005)
- Administration operations center: `admin.*` dashboard/registry/audit/health
  views; SW-026/027/028; migrations 0024–0026. 83/83 tests.

## [0.8.0] — Sprint 7 · Proposal Engine (WF-004)
## [0.7.0] — Sprint 6 · Enterprise Reasoning
## [0.6.0] — Sprint 5 · Retrieval
## [0.5.0] — Sprint 4 · Repository
## [0.4.0] — Sprint 3 · Knowledge Ingestion
## [0.3.0] — Sprint 2 · Database
## [0.2.0] — Sprint 1 · Platform Foundation
## [0.1.0] — Sprint 0 · Repository Bootstrap
