# CRIE — Project Status

> **Living document.** Snapshot of where the project is now. For the stable
> description of the system see [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md).

_Last updated: 2026-07-18._

## Current release

**v1.0.0** — frozen production baseline (git tag `v1.0.0`). The definition of the
freeze lives in [`CANONICAL_BASELINE.md`](CANONICAL_BASELINE.md).

## What is implemented (frozen in v1.0)

- **WF-001 Knowledge Ingestion** — the full ingestion pipeline, portable export.
- **Sub-workflows shipped in this package** (the records changed during bring-up):
  - **SW-005 Azure OCR**
  - **SW-007 LLM Metadata**
  - **SW-008 LLM Knowledge** (v3.5.0, batched extraction)
  - **SW-013 Embeddings**
  - **SW-014 Repository Writer** (v1.1.0)
- The remaining WF-001 sub-workflows (SW-001/002/003/004/006/009/010/011/012/015)
  are unchanged from their last-good state and are part of the ACTIVE set, but are
  **not shipped as files in this package** — they are carried in the n8n instance.
- **Database:** migrations `0001–0028` (definitive DDL chain).
- **Prompts:** `PR-001` at **v1.2** (language preservation) is the only prompt
  shipped as SQL in `prompts/`; the rest of the PR-001…PR-008 catalogue is seeded
  by the environment.
- **Validated runtime config:** worker heap `--max-old-space-size=6144`,
  `QUEUE_WORKER_CONCURRENCY=1`, queue mode, filesystem binary storage.

## Roadmap (not yet built)

Present in `workflows/master/` as **skeletons only** (small placeholder JSON,
mostly `executeWorkflow` stubs pointing at children that do not exist yet). They
define direction, not delivered functionality.

| Next | Family | Notes |
|---|---|---|
| 1 | **WF-002 Enterprise Retrieval** | The next feature workstream. Gated behind the release checklist. |
| 2 | **WF-003 Enterprise Reasoning** | Skeleton. |
| 3 | **WF-004 Output Generation** | Skeleton. |
| — | **WF-005 Administration** | Slightly fuller skeleton (schedule trigger + Postgres nodes); operational/admin tasks. |

## Deferred (explicitly out of the v1.0 freeze)

- Per-batch sub-workflow memory refactor (design complete; removes the need for
  the raised heap).
- Orphan-document sweep (recommended to ship early in operations — see
  [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) §6).
- Adaptive extraction density.
- CI ephemeral-Postgres migration-replay test.
- §406 operational sign-offs (UAT, backup/restore drills, live monitoring,
  queue/circuit-breaker exercise).

## Known operational risks to watch

- **Binding drift on import** — the single most likely deployment failure. Every
  `executeWorkflow` node in WF-001 must be re-bound after import and SW-008 pinned
  by ID. See [`docs/WORKFLOW_INVENTORY.md`](docs/WORKFLOW_INVENTORY.md) and
  [`docs/IMPLEMENTATION_NOTES.md`](docs/IMPLEMENTATION_NOTES.md).
- **Large-document heap** under the current single-execution batch loop, mitigated
  by the documented heap/concurrency config until the per-batch refactor lands.
- **Silent `PENDING` documents** on worker crash until the orphan sweep ships.

## Gate before starting WF-002

All MUST items in [`docs/RELEASE_CHECKLIST_v1.0.md`](docs/RELEASE_CHECKLIST_v1.0.md)
must be checked and the Architecture Owner sign-off recorded.
