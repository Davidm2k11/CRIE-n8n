# Sprint 2 — Database

**Tag:** `v0.3.0` · **Effort:** 2 days · **Depends on:** Sprint 1
**Source of truth:** CRIE Enterprise Specification v1.1 (§217–239.1, §150, §227,
§235, §237, §438, §439) and Task Backlog S2-1 … S2-24.
**DoD:** Database fully operational; all migrations execute cleanly; acceptance
tests pass (§150, §238).

## Objective

Implement the complete Supabase schema via ordered migrations, additive per R-15,
with rollbacks, seeds, and acceptance tests — all user-adjustable behavior driven
by configuration and validated by the startup checks.

## What was produced

| Task | Deliverable | Spec / decision |
|------|-------------|-----------------|
| S2-1…S2-17 | Core migrations `0001`–`0017` | §217–236 |
| S2-18…S2-23 | Additive migrations `0018`–`0023` | §239.1, R-15 |
| S2-24 | Rollback for every migration + DB acceptance tests | §239, §238 |
| — | Seed script (YAML → runtime cache) | R-08, §236 |
| — | Config-driven vector index DDL generator | §227 |
| — | DB docs, ER diagram, migration guide | §239 |

23 forward migrations in `database/migrations/`, 23 matching rollbacks in
`database/rollback/`.

## Canonical decisions honored

- **R-05** — `knowledge_units.category` CHECK-constrained to the §438 16-value
  enum; seeded reference table `configuration.knowledge_categories`.
- **R-06** — `citations` keyed on **both** `evidence_id` and `document_id`.
- **R-09** — `embeddings.embedding vector(1536)`.
- **R-13** — chunks/embeddings under `repository` (Ingestion generates, Retrieval
  consumes).
- **R-15** — `0018`–`0023` are purely additive; `0018` only ADDs columns to
  `knowledge_units`; core tables `0003`–`0009` unchanged in structure.
- **R-16** — 9-source authority model in `configuration.authority_sources`,
  scores config-driven from `retrieval.yaml`.
- **R-18** — checkpoints via append-only `monitoring.processing_history`.
- **R-08** — `configuration.*` are the runtime cache; the authored YAML is the
  source of truth, applied by `seed_configuration.py`.

## Deployable & configurable without source changes

Per the sprint directive, every user-adjustable behavior is exposed through
configuration, documented, and validated by the startup checks:

- **Configuration values** — all ten domain YAMLs flow into
  `configuration.configuration` via `scripts/setup/seed_configuration.py`
  (173 idempotent statements). Editing YAML + re-running the seed is the only
  change needed — no SQL or workflow edits.
- **Vector index** (§227) — type/metric/params read from
  `embedding.vectorIndex`; `scripts/setup/apply_vector_index.py` emits the
  matching HNSW/IVFFlat DDL. Verified: switching type is a config-only change.
- **Authority sources** (R-16) — scores editable in `retrieval.yaml`, seeded.
- **Dictionaries** (§444–445) — `database/seeds/dictionaries.yaml`, seeded.
- **RLS toggle** — `security.rowLevelSecurity`.

The Startup Validation (UT-007) was extended to validate the new adjustable DB
config: vector index type/metric, the 9 authority sources, and the 16-value
category reference. `validate_configuration.py` and the workflow Code node both
enforce these; health stays `Healthy`.

## Verify & test

```bash
python3 tests/integration/test_database.py         # static DB acceptance (§238) — 14 checks
bash   tests/integration/test_sprint2_database.sh  # Sprint 2 acceptance — 8 checks
python3 scripts/setup/validate_configuration.py    # startup gate incl. DB config
```

Live execution against Supabase is an operator step (approved scaffolding-then-
provision model); the Migration Execution Guide documents the exact commands and
the §217 stop-on-first-failure rule.

## Intentionally absent (future sprints)

No ingestion/retrieval/reasoning workflows, no prompt bodies, no master/shared
sub-workflow JSON. The seed maps the prompt/workflow registries into the cache
but creates no prompt bodies. The acceptance test asserts no Sprint-3+ artifacts
are present.

## Assumptions

- No live PostgreSQL/pgvector in this environment and no network to install one,
  so migrations are validated **statically** (ordering, rollback pairing,
  additive-only rule, enums, contracts, append-only enforcement, config-driven
  index) and via SQL lint. Live application is the documented operator step.

## Exit state

Sprint 2 complete, tagged `v0.3.0`. **Sprint 3 not started.**
