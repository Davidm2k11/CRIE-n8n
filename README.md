# CRIE v1.0 — Production Baseline Package

Freezes the current working CRIE implementation as **v1.0**. This is a baseline,
not a redesign: every change folded in here was required to make the frozen
v1.1.1 architecture run correctly. WF-002 (Retrieval) begins after the freeze.

## Contents

```
package/
├── README.md                         ← this file
├── migrations/                       ← 0001–0028 (definitive DDL chain)
├── prompts/
│   └── PR-001_v1.2_language_preservation.sql   ← current production PR-001
├── workflows/                        ← ACTIVE workflow JSON (import these)
└── docs/
    ├── MIGRATION_CHAIN.md            ← (3) reproduce the DB from scratch
    ├── DEPLOYMENT_GUIDE.md           ← (2) clean-environment bring-up
    ├── WORKFLOW_INVENTORY.md         ← (4) active vs archive + binding fix
    ├── SRD_CHANGES_SINCE_SPEC.md     ← (5) every change since the spec
    └── RELEASE_CHECKLIST_v1.0.md     ← (6) freeze gate before WF-002
```

## Order of operations for a clean deploy

1. `docs/DEPLOYMENT_GUIDE.md` — follow start to finish.
2. It references `docs/MIGRATION_CHAIN.md` for the DB and
   `docs/WORKFLOW_INVENTORY.md` for the workflow bindings.
3. Gate the release on `docs/RELEASE_CHECKLIST_v1.0.md`.

## The one thing most likely to bite

After importing workflows, **re-bind every Execute Workflow node in WF-001** to
the freshly-imported children and **pin `SW-008 LLM Knowledge` by ID** to v3.5.0.
Imports mint new workflow IDs; an unpinned binding silently calls a stale
sub-workflow. See `docs/WORKFLOW_INVENTORY.md`.

## Scope of this freeze

IN: migrations 0001–0028, PR-001 v1.2, the ACTIVE workflow set, the operational
config (heap 6144 / concurrency 1).

DEFERRED (post-v1.0): per-batch sub-workflow memory refactor, orphan-document
sweep, adaptive extraction density, CI migration-replay, §406 operational
sign-offs, WF-002 Retrieval.
