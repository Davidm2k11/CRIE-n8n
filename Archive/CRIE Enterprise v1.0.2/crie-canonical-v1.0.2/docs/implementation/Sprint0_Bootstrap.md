# Sprint 0 — Repository Bootstrap

**Tag:** `v0.1.0` · **Effort:** 0.5 day · **Depends on:** none
**Source of truth:** CRIE Enterprise Specification v1.1 (§618, §619–639) and
Task Backlog Sprint 0 (S0-1 … S0-9).

## Objective

Initialize the repository and development environment. No business logic is
written (§637).

## What was produced

| Task | Deliverable | Spec |
|------|-------------|------|
| S0-1 | Git repository initialized | §618, §639 |
| S0-2 | Root folder hierarchy (`snake_case`) | §619–633, §634 |
| S0-3 | Metadata files: README, CHANGELOG, VERSION, LICENSE, .gitignore, .env.example | §635 |
| S0-4 | 10 empty configuration YAML files + empty prompt folders | §627, §626 |
| S0-5 | Empty workflow folders: master, shared, utilities, templates, credentials, documentation | §622–625 |
| S0-6 | database, tests, deployment, benchmark, schemas, scripts folder trees | §621, §628–633 |
| S0-7 | Supabase init — scaffolding + setup docs (live provisioning is an operator step) | §639 |
| S0-8 | n8n workspace init — scaffolding + setup docs (live provisioning is an operator step) | §639 |
| S0-9 | VERSION = `v0.1.0`; README describes setup | §635 |

## Naming conventions enforced (§634)

- Folders: `snake_case`
- Files: `PascalCase.md`, `snake_case.sql`, `WF-XXX_Name.json`, `SW-XXX_Name.json`
- Workflow IDs never change after publication.

## Empty-folder preservation

Git does not track empty directories. Each otherwise-empty leaf folder carries
a `.gitkeep` so the §619–633 hierarchy is preserved exactly in version control.

## Verification & test

```bash
bash scripts/setup/verify_bootstrap.sh   # structural verification vs §619–637
bash tests/integration/test_bootstrap.sh # Sprint 0 acceptance test
```

Both must exit 0 for the sprint to be complete.

## Canonical decisions honored

- **R-08** — configuration YAML is the authored source of truth; the 10 files
  are created empty here and authored in Sprint 1.
- **R-01** — the §624 shared-workflow list is only an "initial scaffold subset";
  the canonical catalog is Module 13 (SW-001…SW-028). No SW files are written in
  Sprint 0 (empty folders only), so no ID conflict is introduced.
- **R-02** — master folder will hold five workflows (WF-001…WF-005); folders
  only in Sprint 0.

## Deviations / assumptions

- **LICENSE:** the spec mandates the file (§635) but names no license. A
  proprietary "all rights reserved" placeholder was used; replace before any
  external distribution.
- **S0-7 / S0-8:** external services (Supabase, n8n) are not network-provisioned
  in this environment. Repository scaffolding, deployment placeholders, and
  step-by-step setup instructions (README + docs/deployment) are in place; the
  live project/workspace creation is an operator action.

## Exit state

Sprint 0 complete, tagged `v0.1.0`. **Sprint 1 not started.**
