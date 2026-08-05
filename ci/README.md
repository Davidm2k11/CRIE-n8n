# CRIE CI Regression Guards

Additive quality tooling — **Iteration 1**. Nothing here modifies a frozen
artifact; it only *validates* the repository. Two guards, runnable identically in
CI (`.github/workflows/ci.yml`) and locally.

## What the guards catch

### 1. Workflow static validation — `ci/validate_workflows.py`
Compile-time checks over the workflow JSON, catching defects that otherwise only
surface at runtime:
- broken / stale `$('Node Name')` references (renamed, deleted, or cross-workflow),
- nodes with no path from any trigger (dead nodes),
- `executeWorkflowTrigger inputSource` set to the camelCase `passThrough` that n8n
  silently ignores (must be lowercase `passthrough`, `typeVersion ≥ 1.1`),
- IF/Switch v2 nodes with a malformed (flat-array) `conditions` that evaluates
  vacuously TRUE,
- prompt-load correctness (SW-007 → PR-002, SW-008 → PR-001; SW-005/013/014 → none),
- **unresolvable `executeWorkflow` bindings** — a symbolic CRIE label (`"SW-016"`) is a
  roadmap-skeleton placeholder, not an n8n workflow ID, so the call can never resolve;
  empty resource-locator values are caught too. When the node *also* carries
  `onError`/`continueOnFail` the finding says so explicitly, because that combination
  fails **silently at runtime**: n8n emits the caller's own input in place of the child's
  output and downstream logic reasons about the wrong payload. This was the WF-005 PR-1
  defect (a false "Orphan sweep did not complete" while SW-016 was healthy) and is the
  same class as the documented #1 deployment failure. `mode:'list'` (name-cached)
  bindings are reported as a **note**, not an error — they are the frozen WF-001
  convention, but they resolve by name and can silently pick a stale duplicate.
- **multi-parent nodes that read the whole input** (`$input.all(` / `$items(`) — reported
  as a **warning**, not an error. A node with multiple incoming parents executes once per
  incoming branch, so `$input.all()` returns only the current branch's items. That is
  perfectly safe for a loop-back or a mutually-exclusive convergence (only one parent ever
  delivers) and unsound for a parallel fan-in whose code reasons across branches — so the
  validator explains both readings and asks the author to confirm which applies, rather
  than assuming every use is wrong. See `docs/IMPLEMENTATION_NOTES.md`,
  "Execution semantics".

### Finding severities
`ERROR` fails the build. `WARN` is potentially unsafe and needs author confirmation;
`NOTE` is informational. Neither advisory level changes the exit code.

**Scope — configuration-driven.** Which workflows count as "active" is defined in a
single file, **`ci/active_workflows.txt`** — a manifest of glob patterns (one per
line, `#` comments, `**` supported), resolved from the repo root. The CI job and
both local runners invoke `validate_workflows.py` with **no path arguments**, so all
three read that manifest; it is the single source of truth. (Explicit path arguments
still override it, for ad-hoc single-file checks.)

To bring a new production workflow under validation, **add a line to
`ci/active_workflows.txt`** — do not edit `ci.yml` or the runners.

The manifest currently covers `workflows/master/WF-001*.json` and
`workflows/subworkflows/**/*.json` (which includes `SW-016 Orphan Sweep`). The roadmap
**skeletons** (`WF-002/003/004`) are intentional placeholder stubs, not production
workflows; validating them as if they were would raise false failures (dead nodes, and
the placeholder bindings they use by convention), so they stay out of the manifest until
they become real workflows.

**WF-005 is held out for a different reason** and is commented out in the manifest with
that reason recorded. It is *not* a skeleton — it is fully wired, and it is precisely the
workflow the binding guard exists to protect. It is held out because its Orphan Sweep node
still carries the unresolvable placeholder `"SW-016"`, which the guard correctly fails on,
and the repository must not adopt an instance-specific workflow ID ahead of the deferred
canonical-ID ADR. Whichever repo-side binding form that decision produces, WF-005 goes
back into the manifest at that point.

### 2. Migration replay — `ci/replay/` + the chain
Proves the migration chain reproduces the database from empty, on real
PostgreSQL 16 **with pgvector**:
1. `bootstrap.sql` — creates the Supabase-provided roles (`service_role`,
   `authenticated`, `anon`) that migration `0014`'s RLS policies require. Applied
   only to the disposable replay DB; it is **not** a migration.
2. Apply `migrations/*.sql` in numeric order with `ON_ERROR_STOP=1` — **twice**.
   The second pass proves the "additive & idempotent" claim (a clean no-op).
3. `verify.sql` — post-replay invariant assertions: the four critical objects
   exist, embeddings are `vector(1536)`, the §438 taxonomy CHECK holds exactly 16
   values, the `processing_history` append-only trigger is present, and migration
   `0029`'s orphan-sweep view + function exist.

This is what verifies migration `0029` — and every future migration — replays
cleanly. A new `0030+` is picked up automatically (the chain is globbed), so a
migration cannot merge without proving it applies on an empty database.

## Running locally

Prerequisites: Python 3.x, the `psql` client, and a reachable PostgreSQL 16 with
pgvector. Easiest database:

```bash
docker run --rm -d --name crie-ci -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=crie_ci -p 5432:5432 pgvector/pgvector:pg16
```

**Windows (PowerShell):**
```powershell
$env:PGURL = "postgres://postgres:postgres@localhost:5432/crie_ci"   # optional
./ci/run_local.ps1
```

**Linux / macOS / Git Bash:**
```bash
PGURL=postgres://postgres:postgres@localhost:5432/crie_ci bash ci/run_local.sh
```

Both runners execute the exact checks CI runs. The replay DB should be empty on
first run; re-running is safe (idempotency is exactly what pass 2 proves).

## When CI runs
On pull requests targeting `main` and on pushes to `main`. Both jobs are blocking.

## If the validator flags a **frozen** workflow
Per the repository precedence rule, a disagreement between this tooling and a
known-good frozen workflow is a **tooling** issue, not a workflow bug. Do **not**
edit a frozen artifact to satisfy the validator — report it and adjust the guard.

## Deferred to Iteration 2 (not built here)
- `pgcheck.py` — prompt/repair SQL lint (adjacent-literal + literal `{{` guard).
- `docs/taxonomy_preflight.sql` — create the file referenced by
  `docs/MIGRATION_CHAIN.md` (the 16-value invariant is asserted in `verify.sql`
  in the meantime).
- Static validation of the roadmap skeletons once they become real workflows.
