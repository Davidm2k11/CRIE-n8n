# CLAUDE.md — Working in the CRIE repository

Guidance for Claude Code (and humans) working in this repo. Start here, then read
the document that owns the concern you're touching.

## What this repo is

CRIE is a **compliance knowledge platform**: n8n workflows over a governed
PostgreSQL 16 + pgvector database. This repo is the **frozen v1.0 baseline**
(migrations, prompts, the ACTIVE workflow set, and docs). See
[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) for the full picture.

## Repository Precedence

The git repository is the single source of truth. When implementing any feature:

1. **Inspect the repository** (code, migrations, workflow JSON) first.
2. **Read the project foundation documents** for intent and constraints.
3. **If implementation and documentation differ, never silently update one to
   match the other.** Report the inconsistency and get a decision before changing
   either.

## Documentation map — where to look

| Concern | Document |
|---|---|
| What CRIE is / long-term architecture | [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) *(stable)* |
| Current state, roadmap, deferred items | [`PROJECT_STATUS.md`](PROJECT_STATUS.md) *(living)* |
| What the frozen baseline contains + rules | [`CANONICAL_BASELINE.md`](CANONICAL_BASELINE.md) |
| Current release summary | [`VERSION.md`](VERSION.md) |
| Why key choices were made (ADRs) | [`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md) |
| Implementation details & gotchas | [`docs/IMPLEMENTATION_NOTES.md`](docs/IMPLEMENTATION_NOTES.md) |
| Corrections since the spec | [`docs/SRD_CHANGES_SINCE_SPEC.md`](docs/SRD_CHANGES_SINCE_SPEC.md) |
| Clean deploy | [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) |
| DB replay from empty | [`docs/MIGRATION_CHAIN.md`](docs/MIGRATION_CHAIN.md) |
| Active vs archive + binding fix | [`docs/WORKFLOW_INVENTORY.md`](docs/WORKFLOW_INVENTORY.md) |
| Freeze gate | [`docs/RELEASE_CHECKLIST_v1.0.md`](docs/RELEASE_CHECKLIST_v1.0.md) |

## Repository layout

```
migrations/            0001–0028 — definitive DDL chain (additive, idempotent)
prompts/               PR-001 v1.2 (production prompt SQL)
workflows/master/      WF-001 (implemented) + WF-002..005 (roadmap skeletons)
workflows/subworkflows/WF-001 SWs/  SW-005/007/008/013/014 (shipped changed set)
docs/                  guides, architecture decisions, implementation notes
archive/               prior packaged versions and reference material
```

## Rules that must not be broken

These are enforced by the baseline; violating them corrupts the release. Full
rationale in [`CANONICAL_BASELINE.md`](CANONICAL_BASELINE.md) and
[`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md).

1. **Migrations are additive.** Never edit a released migration (`0001–0028`).
   Ship corrections as new, higher-numbered files.
2. **Do not widen the §438 16-value taxonomy CHECK** to fix data — fix the
   prompt/enum instead.
3. **`vector(1536)`** embeddings are fixed.
4. **After importing workflows, re-bind every `executeWorkflow` node in WF-001 and
   pin SW-008 by ID.** This is the most common deployment failure.

## Known-good runtime facts — do NOT "fix" these

- **Never send SQL containing `{{` through an n8n Postgres node** — n8n
  interpolates it. The `chr()`-built `{{ocr}}` placeholder exists for this reason.
- **Prompt/repair SQL is dollar-quoted** (Postgres rejects adjacent literals).
- **The Code node has no `crypto`;** read binary via `getBinaryDataBuffer`.
  Postgres/HTTP/Set nodes drop binary.

See [`docs/IMPLEMENTATION_NOTES.md`](docs/IMPLEMENTATION_NOTES.md) for the full
list and the reasons.

## Before you change something

- **Docs:** keep the separation of concerns above. Stable facts → `PROJECT_CONTEXT`
  / `ARCHITECTURE_DECISIONS`; changing state → `PROJECT_STATUS` / `VERSION`;
  gotchas → `IMPLEMENTATION_NOTES`. Don't duplicate procedures already in `docs/`.
- **Database:** add a new migration; verify against
  [`docs/MIGRATION_CHAIN.md`](docs/MIGRATION_CHAIN.md).
- **Workflows:** preserve the frozen contract (passthrough trigger,
  `waitForSubWorkflow: true`, bind-by-ID). See
  [`docs/WORKFLOW_INVENTORY.md`](docs/WORKFLOW_INVENTORY.md).
- **Releasing:** gate on [`docs/RELEASE_CHECKLIST_v1.0.md`](docs/RELEASE_CHECKLIST_v1.0.md).

## Environment notes

- Primary shell is **PowerShell** on Windows; a Bash tool is also available.
- This is a git repo on `main`, tagged `v1.0.0`. Commit/push only when asked.
