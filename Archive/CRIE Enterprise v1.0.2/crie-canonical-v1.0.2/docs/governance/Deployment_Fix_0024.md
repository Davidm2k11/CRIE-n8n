# Deployment Fix Report — Migration 0024 (`admin_dashboard_views`)

_Trigger: deploy of canonical CRIE v1.0.0 failed at migration 0024 with_
_`ERROR: relation "repository.repository_health" does not exist`._
_Scope: minimal deployment fix to 0024 only. No redesign, no other migration touched._
_Result: v1.0.1 (deployment hotfix)._

## 1. Audit of 0024

The reported error is the **first** of a cluster. Migration 0024 (Sprint 8) was
authored against a **richer schema than the frozen migrations 0001–0023 (plus
additive 0026/0027) actually create**. Verified against the migration files, its
view bodies reference:

**7 objects that do not exist in the frozen schema**

| Referenced | Reality |
|---|---|
| `repository.repository_health` (used as a table) | It is a **function** `repository.repository_health()` (0015) **and** a **view** `repository.vw_repository_health` (0016). You cannot `SELECT … FROM repository.repository_health`. |
| `repository.review_queue` | Never created in any migration |
| `repository.requirements` | Never created |
| `repository.proposals` | Never created |
| `monitoring.telemetry` | Never created |
| `configuration.reasoning_config` | Never created |
| `configuration.benchmark_targets` | Never created (benchmark targets live in `monitoring.benchmark_results.target_value`, added by Sprint 9's 0027) |

**~9 columns that do not exist on objects that do exist**

| Referenced | Real column |
|---|---|
| `repository.repository_health.status` / `.health_score` | health surface exposes `(component, state, checked_at)`; no `status`, no `health_score` |
| `monitoring.health_checks.status` | `state` |
| `monitoring.health_checks.service` | `component` |
| `monitoring.health_checks.latency` | (no such column) |
| `monitoring.ai_requests.confidence` | (no such column) |
| `monitoring.ai_requests.latency_ms` | `latency` |
| `monitoring.ai_requests.success` | (no such column) |
| `monitoring.workflow_logs.created_at` (+ `workflow_name`, `workflow_version`, `runtime_ms`, `total_cost`, `*_payload`, `prompt_version`, `repository_version`) | real columns are `timestamp`, `duration`, `status`, `level`, `error`, `retry_count`, `provider`, `model` |
| `repository.documents.lifecycle_state` | `documents` has only `status`; `lifecycle_state` is a **knowledge_units** column (added by 0018) |
| `repository.knowledge_units.language` | (never added; `category`/`authority_source`/`lifecycle_state` exist) |
| `monitoring.benchmark_results.value` / `.run_at` | `metric_value` / `recorded_at` |

**Why it was never caught before deploy:** the Sprint 8 acceptance test only does
text `in` checks on the migration file (view names present, no `INSERT INTO
admin.`, no `DROP`); it never executes the SQL against a database, so
column-level correctness was never validated.

## 2. The minimal deployment fix

Only the **SELECT bodies** of the 11 `admin.vw_*` views were changed. For each
broken reference:

- **A real equivalent exists** → repoint to it: `repository.vw_repository_health`
  (`.state`); `health_checks.state`/`.component`; `ai_requests.latency`;
  `workflow_logs.timestamp`/`.duration`; `documents.status`; certified-document
  count sourced from `knowledge_units.lifecycle_state` (where that column lives);
  `benchmark_results.metric_value`/`.target_value`/`.recorded_at`/`.passed`.
- **No v1 data source exists** (health score, review queue, requirements/
  proposals per-unit cost, telemetry latencies, AI success rate, workflow names/
  payloads, `knowledge_units.language`) → expose a typed `NULL`/`0` placeholder.
  Nothing is fabricated and **no table or column is invented** (that would be a
  redesign, which is out of bounds).

**Preserved:** every view's name and full output-column contract; object kinds;
additive + read-only nature; the rollback (drops by name, unchanged); all other
migrations, workflows, prompts, config, and contracts. BI bindings (R-17) and the
Sprint 8/9 acceptance suites are unaffected.

## 3. Answer to the specific question

> Should the fix reference `vw_repository_health`, or should another object have
> existed?

**Reference `repository.vw_repository_health`** — with two corrections the
suggested swap alone would miss:

1. The name `repository.repository_health` collides with a **function**; the
   selectable object is the **view** `vw_repository_health`. So the object fix is
   correct.
2. That view's column is **`state`**, not `status`, and there is **no
   `health_score` column anywhere in SQL**. The numeric repository health *score*
   is computed in the repository health-statistics / BI layer (see
   `computeHealthScore` in the Sprint 4 repository module), not materialized in
   the schema. So `platform_status` reads `state`, and `repository_health`
   (the score) is exposed as `NULL` in SQL and surfaced by the BI tool (R-17).

No *other* object "should have existed" under the frozen v1 architecture. The
remaining six missing objects (`review_queue`, `requirements`, `proposals`,
`telemetry`, `reasoning_config`, `benchmark_targets`) are **future-scope
features** (§21), not omissions from Sprint 8's frozen deliverable — inventing
them would be a redesign. They are therefore handled as empty (`NULL`/`0`)
projections until those features ship.

## 4. Verification

- Static column-bind check of every qualified and aliased reference in the
  corrected 0024 against the real catalog (migrations 0001–0027): **clean** — no
  phantom objects, no unknown columns, no unknown FROM/JOIN targets.
- Acceptance gate **9/9 (265 tests)**; Sprint 8 suite **83/83**; startup
  validation **Healthy**.
- (No live PostgreSQL in the build environment; the static bind-check substitutes
  for a live parse. Running 0024 against a real instance is the final deploy
  confirmation.)

## 5. Recommendation (not applied — out of the requested scope)

Add a live-database migration test to CI that actually **applies** the migrations
against an ephemeral PostgreSQL and selects one row from each `admin.vw_*` view.
The current Sprint 8 test's text-only checks cannot catch column-level drift;
this is the gap that let the defect reach deployment.
