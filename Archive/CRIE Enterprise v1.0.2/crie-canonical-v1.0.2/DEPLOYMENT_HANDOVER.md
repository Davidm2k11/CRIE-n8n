# CRIE — DEPLOYMENT HANDOVER

_Purpose: hand this project to a new chat/engineer with zero dependence on prior
conversation. Everything needed to continue is below._
_Prepared: 2026-07-09. Authoritative spec: CRIE Enterprise Specification v1.1.1
(frozen; reconciliations R-01…R-18). Architecture Owner: Dawod Manasra._

---

## 0. TL;DR

- **Repository version: `v1.0.1`** (deployment hotfix on top of the v1.0.0
  production release).
- **All 10 sprints are complete.** The build-side acceptance gate is green
  (9/9 suites, 265 tests) and R-14 startup validation is Healthy.
- **The one live-deployment blocker — migration `0024` failing with
  `relation "repository.repository_health" does not exist` — has been root-caused
  and FIXED** in the canonical repo (see §5–§6). It has been statically
  bind-checked but **not yet run against a live PostgreSQL**.
- **Production is NOT yet deployed.** Remaining work is deployment-side:
  apply migrations on real infra, seed config, import workflows, run drills and
  UAT, and record the §406 operational sign-offs.

---

## 1. Current repository version

`v1.0.1` (see `VERSION`). History: v0.1.0 (Sprint 0) → … → v0.10.0 (Sprint 9) →
**v1.0.0 (Sprint 10 — Production Hardening)** → **v1.0.1 (migration 0024
deployment hotfix)**.

Latest delivered bundle: `crie-canonical-v1.0.1.tar.gz` (280 files). It supersedes
`crie-canonical-v1.0.0.tar.gz`, which superseded `crie-canonical-v0.10.0.tar.gz`.

---

## 2. What has been COMPLETED

**Sprints 0–9** — full CRIE platform: platform foundation, database (28 additive
migrations), knowledge ingestion (WF-001), repository (WF-002 + Repository API),
retrieval (WF-002), reasoning (WF-003), output/proposal (WF-004), administration
(WF-005 + `admin.*` dashboard views), benchmarking & UAT framework.

**Sprint 10 — Production Hardening (v1.0.0)** added, and preceded by a full
repository audit:
- `deployment/` layer: `docker/` (Dockerfile + pinned requirements),
  `docker-compose/` reference stack (Postgres+pgvector, Redis, n8n main+worker in
  **queue mode**, R-18) with `production/` and `development/` overrides,
  `supabase/init/`, `n8n/` env reference, and idempotent `scripts/`
  (`apply_migrations`, `rollback_migrations`, `seed_config`, `import_workflows`,
  `smoke_test`, `entrypoint`).
- `.github/workflows/ci.yml` — the §200 CI/CD pipeline (stop-on-fail; protected
  production deploy).
- `tests/run_all.py` — unified acceptance gate (9 suites); `tests/_pathsetup.py`
  — package-reconstruction bootstrap for the flattened Python modules.
- Docs: Deployment Guide, Operations Guide, Backup & Recovery Guide, API Guide,
  and governance reports (Repository Audit, Security Review, Production Readiness).

**Sprint 10 audit fixes (v1.0.0, behavior-preserving — no architecture change):**
the v0.10.0 integration had left the canonical repo's own acceptance suites and
R-14 validator **non-runnable/failing** due to stale pre-integration paths.
Twelve findings; eleven fixed (broken module/test/config paths, non-importable
repository layer, the R-14 validator reporting Critical on valid config, an
over-strict §634 folder check, stale migration-count expectation), one recorded
as non-blocking (mixed contract representation). Details in
`docs/governance/Repository_Audit_Report.md`.

**Migration 0024 deployment hotfix (v1.0.1)** — see §5–§6.

---

## 3. What has been VERIFIED (build environment)

- **Acceptance gate 9/9, 265 tests** (`python3 tests/run_all.py`): Sprint 0
  bootstrap PASS · Sprint 2 database 14/14 · Sprint 3 WF-001 17/17 · Sprint 4
  repository 21/21 · Sprint 5 retrieval 18/18 · Sprint 6 reasoning 32/32 ·
  Sprint 7 output 30/30 · Sprint 8 administration 83/83 · Sprint 9 benchmarking
  & UAT 50/50.
- **R-14 startup validation: Healthy** (`python3 scripts/setup/validate_configuration.py`).
- **Benchmark harness runs clean**; frozen §196 numeric targets unchanged.
- **Migrations 0001–0028 continuous; 28 migrations / 28 rollbacks** (parity).
  Additive-only invariant holds (0001–0023 unchanged; only 0024–0028 added, R-15).
- **Invariants:** prompt catalog PR-001…PR-008 only (R-04, no new IDs); 5 master
  workflows + UT-007; `vector(1536)` lock-in (R-09); dashboards are read-only
  `admin.*` views (R-17).
- **Migration 0024 (the fix): static column-bind check clean** — every qualified
  and aliased reference resolves against the real schema catalog (0001–0027); no
  phantom objects, no unknown columns, no unknown FROM/JOIN targets. Extracted
  v1.0.1 bundle independently passes the gate.
- Deployment scripts pass `bash -n`; compose files parse; `smoke_test.sh` passes
  its config-validation check (DB/n8n checks skipped without live infra).

---

## 4. What has NOT been verified (requires live infrastructure)

These are all **deployment-side** and cannot be done in the build environment
(no live PostgreSQL, n8n, Redis, or LLM/OCR providers here):

1. **Migration 0024 (and the full 0001–0028 set) actually executing against a
   live PostgreSQL.** The fix is static-bind-checked only. **This is the single
   highest-priority verification** — see §11 step 2.
2. Live benchmark/latency/load throughput against real provider adapters (§401).
3. Queue mode + checkpoints + circuit breaker exercised on live n8n (R-18/
   §369–384, task S10-7).
4. Backup + restore drills (§406 "backup tested / recovery tested").
5. UAT execution + sign-off for all four §404 roles.
6. Live monitoring / alerting / cost tracking operational in the target env.
7. BI tool binding to the `admin.*` views (R-17) — deployment-side product choice.
8. Google Sheets live I/O (SW-025 produces the payload; live export via adapter).

Items 3–6 are the §406 gate items currently reported **Pending** (not fabricated
as passed) in `docs/governance/Production_Readiness_Report.md`.

---

## 5. Current deployment status & blocker

**Status: NOT deployed to production.** The deploy attempt failed at migration
`0024_admin_dashboard_views.sql`.

**Blocker (RESOLVED IN REPO, pending live re-run):**
```
ERROR: relation "repository.repository_health" does not exist
```
The fix is applied in the canonical repo at v1.0.1. The next action is to re-run
the migrations against the target database to confirm 0024 (and everything after)
applies cleanly.

---

## 6. Exact root cause discovered

The reported error was the **first** of a cluster. Migration 0024 (authored in
Sprint 8) was written against a **richer schema than the frozen migrations
0001–0023 (+ additive 0026/0027) actually create.** It referenced:

**7 non-existent objects:**
- `repository.repository_health` — used as a selectable table, but it is a
  **function** `repository.repository_health()` (0015) **and** a **view**
  `repository.vw_repository_health` (0016). ← the reported error.
- `repository.review_queue`, `repository.requirements`, `repository.proposals`,
  `monitoring.telemetry`, `configuration.reasoning_config`,
  `configuration.benchmark_targets` — none created by any migration.

**~9 non-existent columns** on objects that do exist:
- `health_checks.status`→ real is `state`; `.service`→ `component`; `.latency`→ none.
- `ai_requests.confidence`→ none; `.latency_ms`→ `latency`; `.success`→ none.
- `workflow_logs.created_at`→ `timestamp` (+ phantom `workflow_name`,
  `workflow_version`, `runtime_ms`, `total_cost`, `*_payload`, `prompt_version`,
  `repository_version`).
- `documents.lifecycle_state`→ `documents` has only `status`; `lifecycle_state`
  is a **knowledge_units** column (added by 0018).
- `knowledge_units.language`→ never added.
- `benchmark_results.value`/`.run_at`→ `metric_value`/`recorded_at`.

**Why it reached deploy:** the Sprint 8 acceptance test only does text `in`
checks on the migration file (view names present, no `INSERT`/`DROP`). It never
executes the SQL, so column-level drift was invisible.

**The correct fix for the reported line:** reference the **view**
`repository.vw_repository_health`, and its column is **`state`** (not `status`);
there is **no `health_score` column in SQL** (the numeric score is computed in the
Sprint 4 repository health-statistics / BI layer, R-17), so it is exposed as
`NULL`. No other object "should have existed" under frozen v1 — the other six are
future-scope features (§21), not Sprint 8 omissions; inventing them would be a
redesign (forbidden).

**Fix applied:** only the SELECT bodies of the 11 `admin.vw_*` views were
rewritten so every reference resolves — real column where one exists, typed
`NULL`/`0` placeholder where v1 has no source. View names, output-column
contracts, object kinds, additive/read-only nature, and the rollback are all
unchanged; no other file touched; no table/column invented.

---

## 7. Files that SUPERSEDE previous versions (changed at v1.0.1)

- `database/migrations/0024_admin_dashboard_views.sql` — **the fix.** Supersedes
  the v1.0.0 copy. (Rollback `database/rollback/0024_admin_dashboard_views_rollback.sql`
  is unchanged and still correct — it drops the 11 views by name.)
- `VERSION` → `1.0.1`.
- `CHANGELOG.md` — adds the `[1.0.1]` entry.
- `REPOSITORY_MANIFEST.txt` — regenerated.
- `docs/governance/Deployment_Fix_0024.md` — **new**, the focused fix report.

Also superseded earlier at **v1.0.0** (relative to the v0.10.0 input), in case the
next chat compares against an old bundle: `scripts/benchmark/config_loader.py`,
`scripts/benchmark/run_benchmark.py`, `scripts/setup/validate_configuration.py`,
`scripts/setup/verify_bootstrap.sh`, all `tests/integration/test_sprint{5,6,7,8,9}_*`
and the two JS suites, `tests/run_tests.py`, `tests/integration/test_database.py`,
`workflows/shared/repository_api.js`, `workflows/shared/repository_writer.js`,
`README.md`, `PROJECT_STATUS.md`; new files `tests/run_all.py`,
`tests/_pathsetup.py`, the whole `deployment/` tree, `.github/workflows/ci.yml`,
and the `docs/` deployment/operations/api/governance set. The self-nested
`crie-canonical-v0_10_0_tar.gz` was removed from the tree.

---

## 8. Canonical source of truth (what to trust)

1. **Governing authority:** `CRIE_Enterprise_Specification_v1_1_1.md` +
   reconciliations R-01…R-18, and the planning docs (Implementation Plan, Task
   Backlog, Implementation Review). The spec is frozen; the § section numbers
   equal the migration's `#` heading numbers.
2. **The canonical repository:** the extracted contents of
   **`crie-canonical-v1.0.1.tar.gz`**. This is the single production codebase.
   Ignore all earlier bundles and any per-sprint overlay bundles.
3. **Live project record:** `PROJECT_STATUS.md` (read it before acting; it is the
   nine-field living record). `CHANGELOG.md` for release history.
4. **Real database schema:** defined solely by `database/migrations/0001…0028`.
   When in doubt about a column, read the migration, not any view or doc.
5. **Acceptance truth:** `python3 tests/run_all.py` (9 suites). The historical
   `test_platform_foundation.sh` / `test_sprint2_database.sh` are point-in-time
   snapshots — non-gating, intentionally not in the gate.

---

## 9. Remaining deployment steps (the runbook)

Follow `docs/deployment/Deployment_Guide.md`. Summary (§200 order; stop on first
failure):

1. **Provision substrate.** Self-hosted:
   `docker compose -f deployment/docker-compose/docker-compose.yml -f deployment/production/docker-compose.prod.yml up -d`.
   Or managed Supabase + managed n8n (point env at them; skip bundled
   postgres/redis). Fill `.env` from `.env.example` (never commit `.env`).
2. **Apply migrations (VERIFY THE 0024 FIX HERE):**
   `DATABASE_URL=… bash deployment/scripts/apply_migrations.sh`.
   Confirm 0001–0028 all apply, especially 0024, with no error. This is the
   direct re-test of the blocker.
3. **Validate + seed config (R-08/R-14):**
   `DATABASE_URL=… bash deployment/scripts/seed_config.sh` (runs startup
   validation first; refuses to seed if invalid).
4. **Build the vector index:** `python3 scripts/setup/apply_vector_index.py`
   (HNSW / `vector(1536)`, R-09).
5. **Import workflows:** `bash deployment/scripts/import_workflows.sh` (or the
   n8n CLI inside the container). Then in n8n: bind provider credentials (never
   in the JSON), activate UT-007 (startup validation) and the scheduled
   dispatcher/telemetry/notification workflows.
6. **Smoke test:**
   `DATABASE_URL=… N8N_HEALTH_URL=… bash deployment/scripts/smoke_test.sh`.
7. **Complete the §406 gate (the "not verified" list, §4 above):** live
   benchmark/load, queue/checkpoint/circuit-breaker exercise (S10-7), backup +
   restore drills, UAT sign-off, live monitoring, BI binding. Record each on the
   protected `production` CI approval.
8. **Promote to production**, then tag/confirm `v1.0.x` and enter the maintenance
   phase (§698/§699).

Ops entrypoint wraps these: `bash deployment/scripts/entrypoint.sh
<migrate|rollback|seed|validate|smoke|gate|benchmark>`.

Rollback if needed: `DATABASE_URL=… bash deployment/scripts/rollback_migrations.sh [NNNN]`
(reverse order; optional stop-at migration number).

---

## 10. Assumptions made

- **The 0024 fix is validated statically, not against a live DB** (no PostgreSQL
  in the build env). Assumption: the real schema matches the catalog derived from
  migrations 0001–0027 (verified by reading the migration files). Live apply in
  step 2 is the confirmation.
- **Confirmed by the Architecture Owner (2026-07-07):** n8n Queue Mode available
  (R-18); a BI platform that consumes Supabase views available (R-17); the
  architecture stays provider-agnostic (all externals via the Provider Adapter
  layer).
- **Dashboard columns with no v1 data source return NULL/0**, deliberately, until
  the corresponding future feature (§21) ships. This is a placeholder, not a bug,
  and not fabricated data.
- **Standalone bundle delivery** is the accepted format; Git commit/tag is applied
  in the canonical repo outside this environment (commit message at
  `scripts/repository/commit_sprint10.txt`).
- **Managed vs self-hosted** are interchangeable with no architecture change; the
  compose stack is the reference, not the only option.

---

## 11. Outstanding risks

- **HIGH — 0024 not yet applied on live PostgreSQL.** The fix is static-checked
  only. Mitigation: step 2 above; if any residual mismatch appears, it will be
  another column/object drift of the same class — re-run the bind logic in
  `docs/governance/Deployment_Fix_0024.md` §4 against the failing object.
- **MEDIUM — CI has no live-DB migration test.** The Sprint 8 text-only test is
  what let 0024's drift reach deploy. Recommended (not yet applied, out of prior
  scope): add a CI job that spins up ephemeral PostgreSQL, runs
  `apply_migrations.sh`, and `SELECT`s one row from each `admin.vw_*` view. This
  would catch this entire defect class permanently.
- **MEDIUM — §406 operational sign-offs pending** (backup/restore drills, UAT,
  live monitoring). Production must not be declared complete until these pass in
  the target env.
- **LOW — mixed contract representation (recorded, non-blocking, O-1).**
  `schemas/contracts/*.contract.json` mix JSON-Schema and instance shapes; their
  consumers pass. Left intact per §617; flagged for a future consolidation ADR.
- **LOW — other Sprint 8 views may share 0024's assumptions.** 0024 is fixed and
  bind-clean. `0026_health_alert_center.sql` was observed during the audit to use
  the same phantom `health_checks` columns (`service`, `status`, `latency`) in
  `admin.vw_health_center`; **it has NOT been fixed** (only 0024 was in scope, and
  0026 did not block the reported deploy). **The next chat should audit 0026 (and
  any other Sprint 8 view migration) with the same live-apply/bind check before
  or during deployment** — it is likely to fail on live apply for the same reason.

---

## 12. Everything else the next chat must know

- **Working style / governance:** strict sprint isolation; additive-only
  migrations; config is the source of truth (edit YAML in `configuration/`, then
  re-run `seed_config.sh` — never author values in tables); prompt catalog frozen
  at PR-001…PR-008; real artifacts only (no scaffolds). Per §617, if something
  conflicts with the frozen spec: stop, explain, propose the smallest compliant
  change, await approval — never silently redesign.
- **Do not regenerate prior sprints.** Treat the repo as a real production
  codebase. Fix only reference/packaging/validation/deployment defects that don't
  change the frozen architecture or feature set.
- **Environment note for the build/analysis sandbox:** no network; no live
  PostgreSQL/n8n/Redis/providers; Python 3.12 (+ PyYAML) and Node 22 available.
  SQL correctness is checked statically (catalog bind-check) here; live apply is
  the real test.
- **Key paths:** migrations `database/migrations/`; rollbacks
  `database/rollback/`; config `configuration/`; workflows `workflows/`
  (master/shared/utilities); prompts `prompts/`; contracts `schemas/contracts/`;
  deployment `deployment/`; tests `tests/` (`run_all.py` is the gate); docs
  `docs/` (deployment/operations/api/governance/implementation).
- **The immediate next action** is deployment step 2 (apply migrations on live
  infra to confirm the 0024 fix), and — recommended — auditing `0026` for the
  same class of defect before it blocks the deploy again.
