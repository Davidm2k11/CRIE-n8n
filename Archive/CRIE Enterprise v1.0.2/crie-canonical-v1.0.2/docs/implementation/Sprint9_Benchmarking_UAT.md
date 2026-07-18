# CRIE Sprint 9 — Benchmarking & UAT

**Version:** v0.10.0 · **Spec:** CRIE Enterprise Specification v1.1.1
**Backlog items:** S9-1 … S9-8 · **Spec refs:** §194–199, §390–406

This sprint delivers the **validation framework** for CRIE. It adds no product
features and changes no architecture. It measures the platform against the
frozen §196 quality targets and produces the Sprint 9 exit-gate artifacts: the
Benchmark Report, the §405 Acceptance Criteria Matrix, and the §406 Production
Readiness Gate.

## Scope (exactly the Sprint 9 backlog)

| Item | Deliverable | Spec |
|---|---|---|
| S9-1 | Unit tests (metric functions) | §194, §391 |
| S9-2 | Integration tests (full benchmark run) | §195, §391 |
| S9-3 | Benchmark datasets + evaluation | §196, §392–400 |
| S9-4 | Load testing | §401 |
| S9-5 | Failure testing | §402 |
| S9-6 | Security testing | §403 |
| S9-7 | User Acceptance Testing scripts | §404 |
| S9-8 | Acceptance Criteria Matrix + Readiness Gate | §405–406 |

Explicitly **not** in scope: Sprint 10 (security review, deployment hardening,
backup/DR execution, `v1.0.0`). No placeholder implementations.

## What was added (all additive — R-15/§239)

### Migrations
- **`0027_benchmark_persistence.sql`** — materializes `monitoring.benchmark_results`
  and `monitoring.latency_history`, which the spec **names** (§130/§3953,
  §7086, §399) but v1.0 never gave columns. Same reconciliation pattern as
  0018–0023. Matching rollback provided (§239).
- **`0028_benchmark_views.sql`** — read-only `admin.*` views surfacing benchmark
  results, latency, the §405 matrix, and the §406 gate to the BI layer;
  plus `monitoring.module_operational_validation` for §405 modules validated
  operationally rather than numerically (see below). Matching rollback provided.

No existing table, view, or workflow from Sprints 0–8 is altered or redefined.
Migration numbering continues the established sequence (Sprint 8 ended at 0026).

### Harness (`benchmark/harness/`)
- `metrics.py` — real metric computations: precision/recall/F1 (§394),
  Recall@k / MRR / NDCG / authority accuracy (§395), citation accuracy (§396),
  hallucination rate (§397), human agreement (§398), cost aggregation (§400).
- `config_loader.py` — loads and validates `config/benchmark.config.yaml` at
  startup (R-08; validation per §327/§157). Fails fast on missing/invalid
  targets.
- `evaluate.py` — evaluates measured values against the **config** targets
  (no hardcoded numbers) and computes the §405 matrix and §406 benchmark gate.
- `run_benchmark.py` — orchestrates a run, emits `monitoring.*` INSERTs, and
  returns matrix + gate.
- `adapter_double.py` — in-memory system-under-test double (real outputs,
  controllable quality) standing in for live providers/datastore.

### Datasets & scripts
- `benchmark/datasets/benchmark_dataset.json` — labeled ground truth across all
  eight §392 document categories × four difficulty tiers, and all ten §393
  requirement types.
- `tests/load/load_harness.py` — §401 scales (10 … 5000).
- `tests/failure/failure_harness.py` — §402 deterministic-recovery model.
- `tests/security/security_harness.py` — §403 checks (positive + negative).
- `uat/uat_scripts.json` — §404 scenarios for all four roles.

### Config (R-08 source of truth)
- `config/benchmark.config.yaml` — the frozen §196/§197/§394–400 targets,
  §392/§393 dataset taxonomy, §401 scales, §402 scenarios, §403 checks, §404
  roles. **Targets transcribed verbatim; unchanged from spec.**

## Design decision: numerically-gated vs operationally-validated modules

§405 requires each module to be "Pass". The §394–400 benchmarks provide numeric
gates for Knowledge Ingestion/Repository (§394), Retrieval (§395), Reasoning
(§397/§398), and Output (§396). Platform Foundation is gated by the §197
latency targets. **Administration maps to Cost (§400), which the spec defines
as *measured/reported*, not numerically gated.** Rather than fabricate a numeric
target for cost — which would violate the S9 DoD ("numbers unchanged from
spec") — Administration is validated **operationally** (§199/§390 functional/
integration/performance validation, resting on the Sprint 8 health, telemetry,
and immutable-audit deliverables). Its pass/fail is recorded in
`monitoring.module_operational_validation` and surfaced by the matrix view.
This keeps every §405 module accounted for without inventing a target.

## BI-platform agnosticism (R-17)

The administration/benchmark contract remains the `admin.*` Supabase views.
n8n produces and refreshes the underlying data; it renders no UI. The initial
deployment may bind Metabase to these views; Power BI or Grafana can replace it
with **no architectural change** — they consume the identical read-only views.
No view carries product-specific logic.

## Honest gate reporting

The §406 gate view computes the benchmark and acceptance-matrix criteria from
data. The remaining operational sign-offs (critical/high defect review, live
UAT approval, backup/recovery drills, live monitoring) are **deployment-side**
and reported as `NULL` → *Pending deployment verification* rather than
fabricated as passed. Those are exercised at Sprint 10 / deployment.

## How to run

```
# Full acceptance suite (offline; no external pytest needed)
python tests/run_tests.py

# Apply migrations (target order continues 0024–0026 from Sprint 8)
psql -f migrations/0027_benchmark_persistence.sql
psql -f migrations/0028_benchmark_views.sql

# Rollback if needed (reverse order)
psql -f migrations/rollback/0028_benchmark_views_rollback.sql
psql -f migrations/rollback/0027_benchmark_persistence_rollback.sql
```

## Acceptance status

**50/50 acceptance tests passing.** Benchmark gate PASS (deployment sign-offs
pending). Exit gate met: Benchmark Report produced (`reports/BENCHMARK_REPORT.md`);
§405 acceptance matrix passes.
