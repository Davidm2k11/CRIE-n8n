# Version

**Current release: v1.0.0** — git tag `v1.0.0`.

Frozen production baseline of CRIE. This file records only the current release.
The full definition of what the baseline contains and the rules that govern it
live in [`CANONICAL_BASELINE.md`](CANONICAL_BASELINE.md); the per-defect change
record lives in [`docs/SRD_CHANGES_SINCE_SPEC.md`](docs/SRD_CHANGES_SINCE_SPEC.md);
the DDL sequence lives in [`docs/MIGRATION_CHAIN.md`](docs/MIGRATION_CHAIN.md).

## v1.0.0 — summary

- **Scope:** first frozen baseline that makes the CRIE Enterprise v1.1.1 design
  run correctly in production (a baseline, not a redesign).
- **Database:** migrations `0001–0028`.
- **Prompt:** `PR-001 v1.2` (language preservation).
- **Workflows:** WF-001 Knowledge Ingestion + the changed sub-workflows
  (SW-005, SW-007, SW-008 v3.5.0, SW-013, SW-014 v1.1.0).
- **Runtime config:** heap `6144`, `QUEUE_WORKER_CONCURRENCY=1`.
- **Next release** will begin with WF-002 (Retrieval); see
  [`PROJECT_STATUS.md`](PROJECT_STATUS.md).
