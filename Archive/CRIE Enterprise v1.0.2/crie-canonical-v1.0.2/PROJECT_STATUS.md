# CRIE Project Status

> Living status document. Update the fields below at the end of every sprint
> (commit → tag → release notes → docs → **status**). Field set is permanent.

_Last updated: 2026-07-09 (deployment hotfix 2 — clean sequential migration apply; v1.0.2)_

## Current Version
`v1.0.2` (deployment hotfix 2 on the v1.0.0 production build; supersedes v1.0.1.
Migrations 0001–0028 now apply cleanly in strict numeric order — the deployment
blocker at 0024 and the same-class drift in 0025/0026 plus the 0012/0027
benchmark-table collision are resolved. Frozen migrations 0001–0023 unchanged.)

## Completed Sprints
- **Sprint 0 — Repository Bootstrap** (`v0.1.0`)
- **Sprint 1 — Platform Foundation** (`v0.2.0`)
- **Sprint 2 — Database** (`v0.3.0`)
- **Sprint 3 — Knowledge Ingestion** (`v0.4.0`)
- **Sprint 4 — Repository** (`v0.5.0`)
- **Sprint 5 — Retrieval** (`v0.6.0`)
- **Sprint 6 — Enterprise Reasoning** (`v0.7.0`)
- **Sprint 7 — Proposal Engine** (`v0.8.0`)
- **Sprint 8 — Administration** (`v0.9.0`)
- **Sprint 9 — Benchmarking & UAT** (`v0.10.0`)
- **Sprint 10 — Production Hardening** (`v1.0.0`)

## Current Sprint
None in progress. **Sprint 10 is complete — this is the final sprint.** Delivered
S10-1…S10-9: the deployment/operations layer and the §204/§407 documentation set,
preceded by a full repository audit against the frozen spec. Sprint 10 fixed only
the audit findings that do **not** change the frozen architecture or feature set
(reference/packaging/validation defects); it added no future functionality, no
placeholders, and no redesign.

**Audit outcome (see `docs/governance/Repository_Audit_Report.md`).** The
v0.10.0 integration had left the canonical repository's own acceptance suites and
R-14 startup validator **non-runnable/failing** because modules and tests kept
pre-integration relative paths. Twelve findings; eleven fixed, one recorded as
non-blocking. No migration, workflow, prompt, contract, or config **value** was
altered. After the fixes the authoritative acceptance gate passes **9/9 suites
(265 tests)** and startup validation reports **Healthy**.

**Sprint 10 deliverables.** `deployment/` (docker, docker-compose incl.
production/development overrides, supabase init, n8n queue-mode reference, and
idempotent scripts: apply/rollback migrations, seed config, import workflows,
smoke test, entrypoint); `.github/workflows/ci.yml` (§200 pipeline, stop-on-fail,
protected production deploy); `tests/run_all.py` (unified gate) and
`tests/_pathsetup.py` (package reconstruction, no logic regenerated); and the
documentation set — **Deployment Guide, Operations Guide, Backup & Recovery
Guide, API Guide**, and the governance reports **Repository Audit Report,
Security Review, Production Readiness Report**. Config `retrieval.yaml`
namespacing fixed in the validator (Healthy); §634 folder check corrected;
self-nested release tarball removed; README refreshed to the canonical v1.0.0.
**No existing table, view, or workflow altered; no new prompt IDs (R-04);
dashboards remain `admin.*` Supabase views (R-17); benchmark numeric targets
unchanged (§196).**

## Latest Git Tag
`v1.0.0` — Sprint 10 · Production Hardening (commit/tag applied in the canonical
repository; project closure per §698).

## Specification Version
CRIE Enterprise Specification **v1.1** (`CRIE_Enterprise_Specification_v1_1_1.md`)
— the sole authoritative source, alongside the Implementation Plan, Task Backlog,
and Implementation Review.

## Architecture Status
**Frozen.** Reconciliation-only revision v1.1; canonical decisions R-01 … R-18
apply. Sprint 10 introduced no architectural change: all fixes are
reference/packaging/validation corrections. No redesign; any deviation requires
explicit Architecture Owner approval.

## Target Deployment Assumptions (confirmed by the Architecture Owner, 2026-07-07)
- **n8n Queue Mode is available** (satisfies R-18). The reference stack runs n8n
  main + workers in queue mode with a Redis backend; queue/checkpoint/circuit-
  breaker behavior is grounded on n8n-native mechanisms and verified in the
  target deployment (S10-7).
- **A BI platform capable of consuming Supabase Views is available** (satisfies
  R-17; dashboards are read-only `admin.*` views surfaced by the BI tool — n8n
  produces data, not UI). Metabase/Power BI/Grafana are interchangeable.
- **The architecture must remain provider-agnostic** — all external services
  (LLM/embedding providers, Google Sheets, BI, datastore) are reached through
  the Provider Adapter layer; no provider-specific logic in workflows, prompts,
  SQL, or code nodes.

## Open Decisions
- **BI tool binding (R-17), deployment-side.** Dashboards ship as read-only
  `admin.*` views; the specific BI product and dashboard definitions are
  provisioned in the target deployment. No architectural decision required; a
  deployment binding confirmation is needed before production.
- **§406 operational sign-offs, deployment-side.** Live UAT approval (§404),
  backup and recovery drills, and live monitoring are confirmed in the target
  environment and recorded on the protected `production` CI approval. The
  readiness reporting shows them **Pending** until confirmed — not fabricated as
  passed.

## Known Risks
- **No live datastore/LLM/n8n in the build environment (accepted).** Benchmarks
  are computed by the real metric functions over the labeled dataset using an
  in-memory adapter double; the same harness runs unchanged against live
  provider adapters at deployment. Live-infra benchmark/load throughput,
  queue/checkpoint/circuit-breaker exercise, and backup/recovery drills are
  performed in the target environment (S10-7, §406 gate items).
- **UAT execution deferred.** §404 scripts are authored for all four roles;
  execution with representative users and sign-off occur in the target
  environment (§406 gate item).
- **Google Sheets provisioning deferred.** SW-025 produces the deterministic row
  payload; live spreadsheet I/O runs through the Provider Adapter layer in the
  target deployment (approved scaffold-then-provision model).
- **Output formatting values** authored in `configuration/output.yaml` (R-08)
  and configurable (§364); deployment confirms final template/column bindings.
- **Confidence weights and review thresholds** authored in
  `configuration/reasoning.yaml` (R-08); unchanged.
- **Cross-encoder reranker** remains config-gated (R-12/§305); unchanged.
- **Embedding dimension lock-in** at `vector(1536)` for v1 (R-09); unchanged.
- **Mixed contract representation (recorded, non-blocking, O-1).**
  `schemas/contracts/*.contract.json` mix JSON-Schema and instance shapes; their
  consumers pass and the delivered contracts were left intact per §617. Flagged
  for a future consolidation ADR; no v1.0 impact.

## Next Sprint Goal
**None — this is the final sprint.** With the deployment-side §406 sign-offs
confirmed in the target environment, the project enters the **maintenance phase**
(§698/§699): apply security updates, review provider compatibility, re-run
benchmarks after major changes, version prompts independently, maintain backward
compatibility where practical, and record architectural changes via ADRs.

## Acceptance Evidence (v1.0.0)
Authoritative acceptance gate — **9/9 suites, 265 tests passing**
(`python3 tests/run_all.py`): Sprint 0 bootstrap PASS · Sprint 2 database 14/14 ·
Sprint 3 WF-001 17/17 · Sprint 4 repository 21/21 · Sprint 5 retrieval 18/18 ·
Sprint 6 reasoning 32/32 · Sprint 7 output 30/30 · Sprint 8 administration 83/83 ·
Sprint 9 benchmarking & UAT 50/50. R-14 startup validation **Healthy**; benchmark
harness runs clean with frozen §196 targets. Migrations 0001–0028 continuous;
28 migrations / 28 rollbacks (parity holds); additive-only invariant holds.

## Repository Integration (2026-07-09)
Canonical repository assembled through Sprint 9 (v0.10.0), then hardened and
certified at Sprint 10 (v1.0.0). §619–635 structure fully populated; the
previously-empty `deployment/` and `.github/` are now delivered (S10-4).
Delivered as `crie-canonical-v1.0.0.tar.gz`.

**Status.** Canonical repository **certified at v1.0.0** and internally
consistent; production-ready pending the deployment-side operational sign-offs
enumerated under Open Decisions / §406. Project closure per §698 upon those
sign-offs.
