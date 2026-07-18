# CRIE — Sprint 8: Administration (Module 50 / WF-005)

_All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying, modification, distribution, or commercial use is prohibited without written permission._

**Version:** `v0.9.0`  ·  **Depends on:** Sprint 7 (`v0.8.0`)  ·  **Spec:** CRIE Enterprise Specification v1.1.1

---

## 1. Scope

Sprint 8 builds the **operations center** for CRIE: the Administration layer defined in Module 50 (§556–§578), delivered as the scheduled master workflow **WF-005 Administration** (R-02) plus the data layer that feeds every dashboard.

Governing decisions:

- **R-02** — Administration is **WF-005** (WF-004 is Output Generation, delivered in Sprint 7).
- **R-17** — Dashboards are **Supabase SQL views surfaced in an external BI tool** (Supabase Studio / Metabase / Grafana). **n8n produces and refreshes the data; it renders no UI.** No dashboard is removed and no metric is dropped — only the presentation mechanism is made explicit.
- **R-18** — The circuit breaker is **provider health state in the `health_checks` table** (breaker `Closed`/`Open`/`HalfOpen`); the queue is the status-column dispatcher + n8n queue mode. Semantics preserved; mechanism stack-native.

This sprint implements **only** Sprint 8 backlog items S8-1 … S8-9. It does **not** implement Sprint 9 (Benchmarking & UAT) — WF-005 only *triggers* the existing benchmark runner and surfaces results; the benchmark **suite** and numeric-target validation (§196/§390–406) remain Sprint 9 scope.

---

## 2. Backlog items delivered

| Task | Item | Artifact(s) | Spec refs |
|---|---|---|---|
| S8-1 | Supabase views for Main / Repository / Workflow / AI / Benchmark dashboards | `migrations/0024_admin_dashboard_views.sql` | §232, §558–§565, R-17 |
| S8-2 | BI surface consuming the views | Views in 0024/0025/0026 are the BI-consumable contract; WF-005 refreshes source data | R-17, §557 |
| S8-3 | Health Center + Alert Center (circuit breaker via `health_checks`) | `migrations/0026_health_alert_center.sql`; WF-005 health + alert nodes | §568–§569, R-18 |
| S8-4 | Repository analytics | `admin.vw_repository_dashboard`, `admin.vw_knowledge_analytics` (0024) | §533, §560 |
| S8-5 | Cost intelligence dashboard | `admin.vw_cost_intelligence`, `admin.vw_ai_dashboard` (0024) | §564, §198 |
| S8-6 | Prompt Registry + Configuration dashboards | `admin.vw_prompt_registry_dashboard`, `admin.vw_configuration_dashboard` (0025) | §570–§571 |
| S8-7 | Audit Center (immutable `audit.*`) | `admin.vw_audit_center` (0025) over `audit.*` (§230/0023) | §572, S2-23 |
| S8-8 | SW-026 Execution Logger, SW-027 Telemetry Collector, SW-028 Notification | `sub-workflows/SW-026…SW-028_*.json` | §266–§268 |
| S8-9 | Config + prompt validation (scheduled) | `scripts/admin_scheduled_validation.py`; WF-005 config/prompt validation nodes | §157, §327 |

---

## 3. Data layer (the dashboards)

All dashboards are read-only views in the new `admin` schema, extending the §232 repository views. They contain **no business logic** — business logic stays in n8n; the views are thin projections/aggregations for BI consumption.

**0024 — operational dashboards & analytics**
`vw_main_dashboard` (§558), `vw_repository_dashboard` (§559), `vw_knowledge_analytics` (§560/§533), `vw_workflow_dashboard` (§561), `vw_execution_explorer` (§562), `vw_ai_dashboard` (§563), `vw_cost_intelligence` (§564/§198), `vw_benchmark_dashboard` (§565), `vw_review_dashboard` (§566), `vw_provider_dashboard` (§567), `vw_operational_kpis` (§577).

**0025 — registry & audit**
`vw_prompt_registry_dashboard` (§570), `vw_configuration_dashboard` (§571 — secrets exposed as *presence only*, never value), `vw_audit_center` (§572, over the four immutable `audit.*` tables).

**0026 — health & alerts**
`monitoring.alerts` table (§569, severity required); additive circuit-breaker columns on `health_checks` (R-18); `vw_health_center` (§568), `vw_alert_center` (§569).

Every migration is **additive** (no table redefined; 0026 only *adds* columns) and ships a matching rollback under `migrations/rollback/` (§239). The 0026 rollback drops the added columns and the alerts table but **preserves** the base §142 `health_checks` table.

---

## 4. Workflow layer

**WF-005 Administration** (`workflows/WF-005_administration.json`) — scheduled (cron from `admin.config.yaml`), following the §159 standard pattern. It:

1. probes services and updates `health_checks` + breaker state (R-18, §568),
2. recomputes repository health (§528) and refreshes statistics/analytics (§529/§533),
3. builds the scheduled cost report (§198/§564),
4. triggers the benchmark runner and surfaces results (§565; Sprint-9 suite not included),
5. runs **config validation** (§327) and **prompt validation** (§157) — S8-9,
6. evaluates configurable **alert thresholds** (§387) and persists **alerts** (§569),
7. dispatches notifications via **SW-028**, logs via **SW-026**, and records telemetry via **SW-027**.

**Sub-workflows (Module 13, S8-8):**
- **SW-026 Execution Logger** (§266) — Workflow / AI / Performance / Audit logs; audit log writes to immutable `audit.*`.
- **SW-027 Telemetry Collector** (§267) — runtime, tokens, cost, provider, model, retry count, success. Cost from config-driven per-model rates (no hardcoded pricing).
- **SW-028 Notification** (§268) — Email (v1); Slack/Teams declared future. Channels reached through the Provider Adapter layer.

---

## 5. Prompts

**No new prompt IDs are introduced.** The eight-prompt catalog (PR-001…PR-008) is frozen (R-04), and prompts are never embedded in workflows (§608/§612). The Administration layer is monitoring/data only; it references the existing registry for the §570 dashboard and validates it (S8-9) but authors no prompt.

---

## 6. Configuration (R-08)

`config/admin.config.yaml` is the authored source of truth, synced into `configuration.*`. It holds the WF-005 schedule, dashboard refresh interval (§558), alert thresholds (§387/§569), circuit-breaker parameters (R-18), the §568 service list, notification channels (§268), export formats (§575), admin roles (§576), and the S8-9 validation toggles. **No hardcoded values** appear in SQL, workflows, or code (Principle 7); secrets are referenced, never stored (§328).

---

## 7. Verification

`tests/test_sprint8.py` — **83/83 passing** (pure stdlib; no live DB/network). Covers migration structure & additivity, rollback presence and base-table preservation, n8n JSON well-formedness and required nodes/connections, config completeness, S8-9 validation logic (positive + negative), and the full **§578 acceptance-criteria matrix**.

`scripts/admin_scheduled_validation.py` runs standalone (exit 0 on the valid fixture) and is the reference for the WF-005 validation nodes.

### §578 Acceptance Criteria — all met
Operational dashboards · Repository analytics · AI cost tracking · Workflow monitoring · Health monitoring · Alerts · Prompt registry · Configuration management · Audit center · Operations center — all operational (views + BI surface + scheduled WF-005).

**Exit gate (DoD):** Administration Console operational (views + BI surface). ✔

---

## 8. Known limits / deferred (accepted)

- **No live datastore/providers in the build environment.** Views and WF-005 are verified structurally and via logic tests; live execution against Supabase/pgvector and live providers is deferred to the infrastructure integration stage.
- **BI tool binding** (R-17) is deployment-side: the views are the contract; the specific BI product and its dashboard definitions are provisioned in the target deployment.
- **Slack/Teams notifications** are declared future (§268); only Email is implemented in v1.
- **PDF export** is reserved future (§575); v1 exports CSV/Excel/JSON.
- **Benchmark suite & numeric targets** (§196/§390–406) are Sprint 9; WF-005 only triggers the runner and surfaces results.
