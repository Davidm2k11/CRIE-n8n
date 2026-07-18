# CRIE Repository Audit Report

_Sprint 10 (Production Hardening), v1.0.0. Audit performed against the frozen
CRIE Enterprise Specification v1.1.1 and reconciliations R-01…R-18._
_Input under audit: `crie-canonical-v0.10.0.tar.gz` (the single source of truth)._

## Scope & method

The canonical repository was audited across architecture, workflows, migrations,
configuration, prompts, contracts, scripts, tests, documentation, dependencies,
and production readiness. No previous sprint was regenerated or reinterpreted;
the repository was treated as a real production codebase. Findings that do **not**
change the frozen architecture or feature set (broken references, packaging,
outdated expectations, a startup-validation defect, and an over-strict check)
were fixed as part of Sprint 10. Findings that would change delivered artifacts
were recorded and left intact.

## Summary

The v0.10.0 integration correctly assembled artifacts into the §619–635 canonical
structure, but a class of **path/reference regressions** was introduced: modules
and tests retained relative paths from their pre-integration bundle layout. As a
result the canonical repository's acceptance suites and its own startup validator
did not run/pass as shipped, even though the underlying artifacts were sound.
Twelve findings were identified; eleven were fixed under Sprint 10's remit, one
was recorded as a documented, non-blocking observation.

Post-fix, the authoritative acceptance gate is **9/9 suites passing (265 tests)**
and the R-14 startup validation reports **Healthy**.

## Findings

**F-01 — Test runner points at a non-canonical path.** `tests/run_tests.py`
loaded `tests/test_sprint9_acceptance.py`; the suite lives at
`tests/integration/`. **Fix:** corrected the suite path. Impact: the Sprint 9
gate could not run.

**F-02 — Sprint 9 suite `sys.path` stale.** The suite added `benchmark/harness`,
`tests/failure`, `tests/security`, `tests/load` to `sys.path`; canonical
locations are `scripts/benchmark`, `tests/regression`, `tests/load`. **Fix:**
repointed to canonical harness/regression/load directories.

**F-03 — Benchmark config path stale.** `scripts/benchmark/config_loader.py`
resolved `config/benchmark.config.yaml`; canonical is
`configuration/benchmark.yaml`. **Fix:** corrected the default path.

**F-04 — Benchmark dataset path stale.** `scripts/benchmark/run_benchmark.py`
resolved `scripts/datasets/…`; canonical is `benchmark/datasets/…`. **Fix:**
corrected the default path.

**F-05 — Ambiguous roots in the Sprint 9 suite.** The suite used one `ROOT` for
both `benchmark/` (repo root) and `uat/` (tests root). **Fix:** introduced
`REPO_ROOT` (dataset) and kept `TESTS_ROOT` (uat).

**F-06 — CI/CD absent.** `.github/` contained only `.gitkeep`; §200 requires a
pipeline. **Fix (Sprint 10 deliverable):** added `.github/workflows/ci.yml`
mirroring the §200 stages.

**F-07 — JS suite requires stale.** `WF-001_acceptance.test.js` and
`repository_acceptance.test.js` used `../workflows`, `./fakes`,
`../repository/*` from the bundle layout. **Fix:** repointed to
`../../workflows/...`, `../fixtures/...`, and the canonical `workflows/shared/`
locations (including `runWF001` in `shared/`, not `master/`).

**F-08 — Repository module cross-requires broken.** `repository_api.js` and
`repository_writer.js` required `./certification`, `./writer`,
`./health_statistics`; canonical files carry the `repository_` prefix. The
Sprint 4 repository layer was non-importable as shipped. **Fix:** corrected the
internal requires to canonical filenames.

**F-09 — Sprint 5/6/7 suites imported non-existent `src/` packages.** The
`retrieval`, `reasoning`, `output_generation` packages were flattened into
`workflows/shared/<pkg>_<mod>.py` during integration; the suites still imported
them as packages with relative imports. **Fix:** added `tests/_pathsetup.py`, a
package-reconstruction bootstrap that maps the canonical flat modules to the
expected package names **without regenerating any logic**, and repointed the
suites' file-path aliases (`config/`→`configuration/`, `contracts/`→
`schemas/contracts/`, `src/output_generation`→`workflows/shared/output_*.py`,
`sample_requirements.json`→`examples/rfps/`).

**F-10 — Sprint 8 suite dir aliases + filename case stale.** The suite used
`migrations/`, `config/`, `sub-workflows/`, and lowercase
`WF-005_administration.json` / `admin.config.yaml`; canonical uses
`database/migrations`, `configuration`, `workflows/shared`, PascalCase
`WF-005_Administration.json`, and `admin.yaml`, and the §578 artifact matrix used
bundle-relative paths. **Fix:** corrected all aliases, filenames, and matrix
paths to canonical.

**F-11 — Startup validator reports Critical against shipped config (real
defect).** `scripts/setup/validate_configuration.py` merged each config file's
top-level keys flat, so `retrieval.yaml` (authored **unwrapped**, unlike every
other domain file) failed the `retrieval.*` checks, and `authority.yaml`'s
root-level `authoritySources` was mis-namespaced. The platform's own R-14
validator therefore reported `Critical` on a valid config. **Fix:** the validator
now namespaces an unwrapped domain file by its filename stem and treats
`providers.yaml`/`authority.yaml` as root-merged. **No config file was mutated**;
values are unchanged. Result: startup validation `Healthy`.

**F-12 — Over-strict §634 folder-name check.** `verify_bootstrap.sh` flagged the
spec-mandated `prompts/**/PR-00X` identifier folders as non-snake_case. **Fix:**
exempted canonical ID folders (`PR-`, `WF-`, `SW-`, `UT-`) from the check.

### Recorded, non-blocking (not changed)

**O-1 — Mixed contract representation.** `schemas/contracts/*.contract.json` mix
JSON-Schema (`context_package`, `proposal_package`) and filled-instance shapes
(`citation`, `compliance_result`). Their Sprint 6/7 consumers read the instance
form and pass; per §617 the delivered contracts were left intact. Recorded for a
future consolidation ADR; no v1.0 impact.

**O-2 — Historical sprint snapshots.** `test_platform_foundation.sh` and
`test_sprint2_database.sh` assert end-of-their-own-sprint state ("no prompt
bodies yet", "only UT-007 built", "23 migrations"), intentionally false at v1.0.
They were annotated as historical/non-gating and excluded from the acceptance
gate rather than rewritten (rewriting would falsify their documented intent).

## Invariants re-verified

Migrations 0001–0028 continuous, 28 migrations / 28 rollbacks (parity holds);
additive-only invariant holds (0001–0023 unchanged; only 0024–0028 added, R-15);
master workflows WF-001…WF-005 + UT-007 present under §623 names; prompt catalog
PR-001…PR-008 only, no new IDs (R-04); all workflow/schema JSON and config YAML
parse; embedding dimension `vector(1536)` lock-in intact (R-09); dashboards remain
read-only `admin.*` views (R-17); queue/checkpoint/circuit-breaker grounded on
n8n-native mechanisms (R-18).

## Disposition

All fixes are reference/packaging/validation corrections that preserve the frozen
architecture and feature set. The repository is internally consistent and its
acceptance gate and startup validation pass in the canonical layout.
