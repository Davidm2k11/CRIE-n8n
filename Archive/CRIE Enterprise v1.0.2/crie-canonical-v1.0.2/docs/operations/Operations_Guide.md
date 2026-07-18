# CRIE Operations Guide

_Deliverable: §407 (Operations_Guide). Sprint 10, v1.0.0._
_Authoritative spec: CRIE Enterprise Specification v1.1.1._

Day-two operations for a running CRIE deployment: monitoring, alerting, the
queue/checkpoint/circuit-breaker mechanics, routine tasks, and troubleshooting.
Dashboards are delivered as read-only `admin.*` Supabase views surfaced by an
external BI tool (R-17); n8n produces data, not UI.

## 1. Monitoring (§386)

Monitor continuously: queue length, OCR latency, embedding latency, retrieval
latency, AI latency, error rate, success rate, cost, and throughput. These are
surfaced by the Administration views delivered in Sprint 8 and the benchmark/
latency views from Sprint 9:

- `admin.vw_main_dashboard`, `admin.vw_operational_kpis` — platform overview.
- `admin.vw_workflow_dashboard`, `admin.vw_execution_explorer` — execution
  health and history.
- `admin.vw_ai_dashboard`, `admin.vw_cost_intelligence` — AI usage and cost.
- `admin.vw_provider_dashboard` — provider health and circuit-breaker state.
- `admin.vw_benchmark_dashboard` and the §405 matrix / §406 gate views — quality
  and readiness.

Bind these views in the BI platform (Metabase/Power BI/Grafana — interchangeable
per R-17). No n8n UI is built.

## 2. Alerting (§387)

Alerts trigger when a monitored value crosses its configured threshold: OCR
queue depth, retrieval time, LLM error rate, repository failure rate, and daily
cost budget. Thresholds are configurable in `configuration/monitoring.yaml`
(R-08) and are persisted/evaluated via the alert-center view and the SW-028
Notification sub-workflow (email in v1; Slack/Teams are future). Editing a
threshold means editing the YAML and re-running `seed_config.sh`.

## 3. Queue, checkpoints, circuit breaker (R-18 / §369–§384)

**Queue (§369/§370).** Long-running work advances through pipeline stages
(`UPLOAD_PENDING` → `OCR_PENDING` → `KNOWLEDGE_PENDING` → `EMBED_PENDING` →
`REPO_PENDING` → `COMPLETED`). A scheduled dispatcher advances items `ORDER BY
priority`. Stages are isolated: a failure in one does not stop the others. Verify
by inspecting stage counts and confirming an injected failure in one stage does
not block another.

**Concurrency / scaling (§371/§382).** n8n queue-mode workers process
independent items in parallel; repository writes stay transactional and never
create duplicates. Scale with `docker compose up --scale n8n-worker=N`.

**Checkpoints (§372).** Each completed stage is persisted to
`processing_history`. On failure the dispatcher re-enters the document at its
last completed stage. Verify by failing a workflow mid-pipeline and confirming it
resumes rather than restarting.

**Circuit breaker (§384).** Adapters record failures in `health_checks`. When a
provider's failure count crosses its configured threshold (§387) its state
becomes `Open` and adapter workflows fail fast; a scheduled recovery test
transitions it back to `Healthy`. Verify by forcing repeated provider failures
and confirming requests short-circuit while `Open`.

## 4. Routine tasks

**Change configuration (R-08).** Edit `configuration/*.yaml`, then
`bash deployment/scripts/seed_config.sh`. Startup validation runs first and
blocks the sync if configuration is invalid (§327).

**Update a prompt (R-04).** Prompt catalog is frozen at PR-001…PR-008; no new
IDs. Version prompts independently (§697/§699) and re-seed the registry.

**Add knowledge.** Upload flows through WF-001; documents become certified
knowledge only after certification (§338). Only certified, non-archived
knowledge is retrievable in production.

**Re-run benchmarks.** `bash deployment/scripts/entrypoint.sh benchmark` (or
`python3 scripts/benchmark/run_benchmark.py`). Numeric targets are frozen (§196)
and read from `configuration/benchmark.yaml` (R-08). Re-run after any major
change (§699) and retain historical reports in `benchmark/reports/` (§631).

**Run the acceptance gate.** `python3 tests/run_all.py` runs all nine
current-state acceptance suites. Use it before and after any change.

## 5. Performance & cost operations (§367–§381)

Performance optimizations never change business behavior (§367). Cache only
deterministic data — configuration, prompt registry, metadata, repository
statistics, health status — never compliance results, AI responses, or
repository transactions (§373). Before any AI call, the platform verifies a valid
Context Package, minimum evidence, and required citations; if validation fails
the LLM is not called (§379). Cost is minimized by skipping duplicate documents,
unchanged embeddings, and repeated retrieval (§378), and by incremental
processing on document change (§380). Certified documents are not re-certified
unless content, extraction logic, or prompt version changes (§381).

## 6. Health checks

`python3 scripts/setup/validate_configuration.py` runs the R-14 startup
validation on demand (config + secrets presence + provider readiness) and prints
overall health. The scheduled Startup Validation workflow (UT-007) performs the
same check on deploy and on schedule; on failure it marks platform health
`Critical`, raises an alert, and downstream master workflows refuse to run
against invalid configuration (§327/§326).

## 7. Troubleshooting

Configuration `Critical`: run `validate_configuration.py`; fix the reported
`missing_config:*` / range / dimension issue in the YAML; re-seed. Workflow
failure: retry, then resume from the last checkpoint (`processing_history`), then
route to human review (§202). Provider outage: expect the circuit breaker to
open and requests to fail fast; recovery is automatic once the provider is
healthy (§383/§384). Empty retrieval: the ordered retry ladder runs and, on
exhaustion, returns `InsufficientEvidence` without calling the LLM (§471).
