# Sprint 10 — Production Hardening (v1.0.0)

_Authoritative spec: CRIE Enterprise Specification v1.1.1. Backlog: S10-1…S10-9._
_Depends on: Sprint 9. Tag: `v1.0.0`._

Sprint 10 prepares production deployment. It adds the deployment/operations layer
and the production documentation, and — as directed — fixes the audit findings
that do not change the frozen architecture or feature set. It implements **only**
Sprint 10 scope; no future functionality, no placeholders, no redesign.

## Repository audit + fixes (pre-implementation)

A full audit against v1.1.1 preceded implementation. Twelve findings; eleven
fixed (reference/packaging/validation), one recorded as non-blocking. Details in
`docs/governance/Repository_Audit_Report.md`. Headline: the canonical repo's own
acceptance suites and R-14 startup validator did not run/pass as shipped due to
unreconciled pre-integration paths; both now pass (gate 9/9, 265 tests; startup
`Healthy`). No config values, migrations, workflows, prompts, or contracts were
altered — only paths, a validator's namespacing, an over-strict check, and stale
test expectations.

## Backlog coverage

| Task | Deliverable |
|---|---|
| S10-1 Security review (§203/§330–350/§403) | `docs/governance/Security_Review.md` |
| S10-2 Performance optimization (§367–381) | Verified + documented in Operations Guide §5; behavior-preserving, config-gated (no code redesign) |
| S10-3 Cost optimization (§378–379) | Verified + documented (dedup/skip, pre-AI validation gate) |
| S10-4 Deployment scripts + CI/CD (§200/§325/§630) | `deployment/` (docker, docker-compose, supabase, n8n, production, development, scripts) + `.github/workflows/ci.yml` |
| S10-5 Backup strategy (§201/§349) | `docs/deployment/Backup_Recovery_Guide.md` + rollback script |
| S10-6 Disaster recovery (§202/§350) | Backup & Recovery Guide §3–§4 |
| S10-7 Verify queue/checkpoint/circuit breaker in target (R-18/§369–384) | Verification procedures in Operations Guide §3; grounded on n8n-native mechanisms; live verification is a target-env gate item |
| S10-8 Documentation review + production checklist (§204/§388/§616) | `docs/governance/Production_Readiness_Report.md` + full §204/§407 doc set |
| S10-9 Tag v1.0.0; release notes; closure (§652/§698) | `VERSION=1.0.0`, CHANGELOG, PROJECT_STATUS; tag applied in canonical repo |

## New / changed artifacts

**New — deployment layer (S10-4/5/6):**
`deployment/docker/Dockerfile`, `deployment/docker/requirements.txt`,
`deployment/docker-compose/docker-compose.yml`,
`deployment/production/docker-compose.prod.yml`,
`deployment/development/docker-compose.dev.yml`,
`deployment/supabase/init/00_create_n8n_db.sql`,
`deployment/n8n/n8n.env.reference`,
`deployment/scripts/{apply_migrations,rollback_migrations,seed_config,import_workflows,smoke_test,entrypoint}.sh`,
`.github/workflows/ci.yml`.

**New — documentation (S10-1/5/6/8):**
`docs/deployment/Deployment_Guide.md`, `docs/operations/Operations_Guide.md`,
`docs/deployment/Backup_Recovery_Guide.md`, `docs/api/API_Guide.md`,
`docs/governance/{Repository_Audit_Report,Security_Review,Production_Readiness_Report}.md`,
this manifest.

**New — test tooling:** `tests/run_all.py` (unified acceptance gate for CI/§406),
`tests/_pathsetup.py` (package-reconstruction bootstrap; regenerates no logic).

**Changed — audit fixes (behavior-preserving):** benchmark harness default paths
(`config_loader.py`, `run_benchmark.py`); Sprint 5/6/7/8/9 test path resolution;
JS test requires + repository module internal requires;
`validate_configuration.py` config namespacing (config `Healthy`);
`verify_bootstrap.sh` folder-name check; `test_database.py` migration list
(23→28, additive); historical snapshot annotations. Packaging: removed the
self-nested `crie-canonical-v0_10_0_tar.gz`; `.gitignore` now excludes release
bundles.

## Invariants (unchanged)

Additive-only migrations (0001–0023 byte-identical; only 0024–0028 added, R-15);
prompt catalog frozen PR-001…PR-008 (R-04); five masters + UT-007 (R-01/R-02);
`vector(1536)` lock-in (R-09); dashboards are read-only `admin.*` views (R-17);
queue/checkpoint/circuit-breaker n8n-native (R-18); provider-agnostic throughout.
Benchmark numeric targets unchanged (§196).

## Exit

Acceptance gate 9/9 (265 tests); startup validation Healthy; benchmark harness
clean; §406 gate Met except the deployment-side operational sign-offs (UAT,
backup/recovery drills, live monitoring), reported as Pending. `VERSION=1.0.0`.
This is the final sprint; the project enters the maintenance phase (§698/§699)
after the target-env sign-offs.
