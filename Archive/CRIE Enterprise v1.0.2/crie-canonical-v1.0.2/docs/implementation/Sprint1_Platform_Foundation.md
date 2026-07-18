# Sprint 1 — Platform Foundation

**Tag:** `v0.2.0` · **Effort:** 2 days · **Depends on:** Sprint 0
**Source of truth:** CRIE Enterprise Specification v1.1 (§12–20, §300–329, §316–327,
§159, §213, §366) and Task Backlog S1-1 … S1-10.
**Exit gate (R-14):** Startup Validation workflow passes (config + secrets +
providers valid); platform health = Healthy.

## Objective

Build the runtime infrastructure that all business logic depends on, before any
business logic is written.

## What was produced

| Task | Deliverable | Location | Spec / decision |
|------|-------------|----------|-----------------|
| S1-1 | Configuration authored as YAML (source of truth) | `configuration/*.yaml` (10 files) | §12, §300–312, R-08 |
| S1-2 | No-hardcoded-values rule enforced; every value read from config | `schemas/yaml/configuration.schema.json`, validator | Principle 7, §621 |
| S1-3 | Prompt Registry structure + versioning (no bodies) | `prompts/registry.yaml` | §13, §172–175, R-04 |
| S1-4 | Logging service — structured-log contract + levels | `schemas/contracts/structured_log.schema.json`, `workflow_error.schema.json` | §15, §309, §19 |
| S1-5 | Telemetry service — telemetry contract | `schemas/contracts/telemetry.schema.json` | §16, Principle 8 |
| S1-6 | Health Monitoring — Health API contract | `schemas/contracts/health_status.schema.json` | §18, §366 |
| S1-7 | Secrets Management — allowed-locations policy | `configuration/security.yaml`, `.env.example` | §14, §321–324, §608 |
| S1-8 | Provider Adapter layer — OCR/LLM/embedding/storage interface | `schemas/contracts/adapter_interface.yaml`, `adapter_error.schema.json` | §316–320, Modules 37–39 |
| S1-9 | Workflow Registry + standard pattern scaffold | `workflows/registry.yaml`, `execution_summary.schema.json` | §152, §159, §213 |
| S1-10 | Startup Validation workflow | `workflows/utilities/UT-007_Startup_Validation.json` + `scripts/setup/validate_configuration.py` | R-14, §326–327, §640 |

## Configuration model (R-08)

Configuration is **authored in YAML** under `configuration/` — the single source
of truth — and is loaded into the `configuration.*` runtime-cache tables by the
seed step in **Sprint 2**. Values are never authored directly in the tables and
never hardcoded in workflows (Principle 7). All ten domain files are authored
with real v1 values: `providers`, `repository`, `retrieval`, `reasoning`,
`monitoring`, `feature_flags`, `logging`, `storage`, `security`, `benchmark`.

Key locked values: embedding `dimensions: 1536` (R-09); all feature flags
default `false` (§312); `rerankerEnabled: false` (rerank is config-gated, R-12).

## Canonical contracts (`schemas/`)

The observability and adapter layer is defined by canonical JSON contracts that
every workflow conforms to: structured log (§15), telemetry (§16), health status
(§18/§366), adapter error (Module 37), workflow error (§19), execution summary
(§216), and the configuration validation schema (§327). These are the shapes the
Sprint 3+ workflows must satisfy.

## Startup Validation (R-14) — the exit gate

`UT-007_Startup_Validation.json` is a real, importable n8n workflow (deploy +
scheduled triggers → validation Code node → Healthy / Critical branches). The
validation logic is factored into `scripts/setup/validate_configuration.py` so it
is runnable and testable before the n8n runtime and the `configuration.*` cache
tables exist. It performs the six §327 checks:

1. required config values exist; 2. embedding dimension = 1536 (R-09);
3. valid log level; 4. structured logging on; 5. feature flags are booleans;
6. reranker gate. Plus ranking-weight sum, endpoint URL validity, and
(deploy-time, `--check-env`) presence of required secrets (§314).

On failure it returns `health.overall = Critical`, an alert, and
`blockExecution = true` — realizing "SHALL stop startup" as "SHALL block
execution and alert when configuration is invalid" (R-14). On success:
`health.overall = Healthy`.

```
$ python3 scripts/setup/validate_configuration.py
Startup Validation: PASS (health.overall = Healthy)
```

## Verify & test

```bash
python3 scripts/setup/validate_configuration.py        # R-14 gate (config-only)
python3 scripts/setup/validate_configuration.py --check-env   # deploy-time (needs secrets)
bash tests/integration/test_platform_foundation.sh     # Sprint 1 acceptance (11 checks)
bash tests/integration/test_bootstrap.sh               # Sprint 0 structural regression
```

Sprint 1 acceptance: **11/11 pass**, including the R-14 exit gate.

## Intentionally absent (owned by later sprints)

Per the instruction to leave future-sprint components absent rather than create
incomplete logic:

- **DB migrations & `configuration.*` / `monitoring.*` tables** — Sprint 2.
  Contracts note where persistence attaches; no SQL is written.
- **Concrete provider sub-workflows** SW-005 (OCR), SW-013 (embedding),
  SW-023 (LLM), SW-025 (Sheets) — Sprints 3/6/7. Only the adapter *interface* is
  fixed now.
- **Prompt bodies** (system.md/user.md/schema.json/examples) — Sprints 3/6/7.
  The registry lists all eight IDs with `latestVersion: null`.
- **Master workflows** WF-001…WF-005 and **UT-001…UT-006** — later sprints;
  registered as `status: planned`.

The acceptance test explicitly asserts none of these leaked into Sprint 1.

## Deviations / assumptions

- **Startup Validation workflow ID:** §625 reserves UT-001…UT-006 with fixed
  names (Logging, Telemetry, Health, Notifications, Benchmark, Backup);
  "Startup Validation" is named a utility workflow by R-14/§329 but is not
  assigned a UT number. It is registered as **UT-007** to avoid colliding with
  the §625-reserved IDs while remaining in the utilities family. Flag for the
  Architecture Owner if a different ID is preferred (IDs are immutable once
  published, §634).
- **`jsonschema` library** is unavailable offline; the §327 checks are
  implemented directly in the validator, and schema files are checked for
  well-formedness. No functional gap.

## Exit state

Sprint 1 complete, tagged `v0.2.0`. Startup Validation passes; health = Healthy.
**Sprint 2 not started.**
