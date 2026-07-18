# CRIE — Canonical Baseline

Defines the **frozen v1.0 baseline**: the exact set of artifacts that constitute
the release, its validation status, and the rules that govern changes to it. If a
working copy diverges from what is described here, the working copy is wrong.

## Baseline identity

| Field | Value |
|---|---|
| Release | **v1.0.0** |
| Git tag | `v1.0.0` |
| Branch | `main` |
| Nature | Production baseline of the CRIE Enterprise v1.1.1 design — corrective, not a redesign |

## Frozen artifacts

### Database — migrations `0001–0028`
The definitive DDL chain, applied in numeric order against an empty PostgreSQL 16
(Supabase) instance. Additive and idempotent. Full table in
[`docs/MIGRATION_CHAIN.md`](docs/MIGRATION_CHAIN.md).

### Prompts
- `prompts/PR-001_v1.2_language_preservation.sql` — the production PR-001 (v1.2).
  `SW-008` loads `ORDER BY version DESC LIMIT 1` → v1.2.
- The rest of the frozen **8-prompt catalogue** (PR-001…PR-008) is seeded by the
  environment's provisioning, not shipped as SQL in this package.

### Workflows

**Frozen ACTIVE set (v1.0):**

| Workflow | Version | Shipped as file |
|---|---|---|
| WF-001 Knowledge Ingestion | v0.10.x (portable export) | yes — `workflows/master/` |
| SW-005 Azure OCR | current | yes — `workflows/subworkflows/WF-001 SWs/` |
| SW-007 LLM Metadata | trigger-fixed | yes |
| SW-008 LLM Knowledge | **v3.5.0** | yes |
| SW-013 Embeddings | trigger-fixed | yes |
| SW-014 Repository Writer | **v1.1.0** | yes |
| SW-001/002/003/004/006/009/010/011/012/015 | unchanged / last-good | no — carried in the n8n instance |

**Not part of the baseline** (roadmap skeletons in `workflows/master/`, excluded
from the freeze): WF-002 Retrieval, WF-003 Reasoning, WF-004 Output Generation,
WF-005 Administration.

### Runtime configuration (part of the frozen baseline)
- Worker `NODE_OPTIONS=--max-old-space-size=6144`
- `QUEUE_WORKER_CONCURRENCY=1`
- n8n Queue Mode, filesystem binary storage

## Validation status

The baseline is validated against the freeze gate in
[`docs/RELEASE_CHECKLIST_v1.0.md`](docs/RELEASE_CHECKLIST_v1.0.md). Key acceptance
facts folded into the freeze:

- Migrations `0001–0028` replay cleanly on an empty PostgreSQL 16.
- `chk_knowledge_units_category` holds exactly the §438 16 values and matches
  `configuration.knowledge_categories` (taxonomy pre-flight passes).
- `repository.embeddings.embedding` is `vector(1536)`.
- English and Arabic documents ingest to `PROCESSED`; Arabic KU statements remain
  Arabic (PR-001 v1.2); a ~60-page document completes without heap OOM under the
  documented config; SW-014 commits its single transaction with no `uuid: ""`
  error.

> Recommended-but-deferred CI guards (ephemeral-Postgres replay, `pgcheck.py`,
> `validate_workflows.py`) are listed in the release checklist §6 and tracked in
> [`PROJECT_STATUS.md`](PROJECT_STATUS.md) as deferred.

## Baseline rules

1. **Additive-only migrations.** `0001–0028` are frozen. Corrections ship as new,
   higher-numbered migrations — never edits to a released migration.
2. **Canonical invariants are not relaxed to fix defects.** The §438 16-value
   taxonomy CHECK, `vector(1536)`, the single Compliance Result contract, and the
   8-prompt catalogue are fixed; drift is corrected in the prompt/enum/workflow,
   not by widening a constraint. See
   [`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md).
3. **Prompts version additively** in `configuration.prompt_versions`; superseded
   versions are retained for audit.
4. **Workflow bindings are pinned by ID.** After any import, re-bind every
   `executeWorkflow` node in WF-001 and pin SW-008 by ID; delete stale copies. See
   [`docs/WORKFLOW_INVENTORY.md`](docs/WORKFLOW_INVENTORY.md).
5. **The tag is the source of truth.** A clean deploy reproduces from tag `v1.0.0`
   via the migration chain and the ACTIVE workflow set — see
   [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md).
6. **WF-002 may begin only after** all MUST items in the release checklist are
   satisfied and the Architecture Owner sign-off is recorded.
