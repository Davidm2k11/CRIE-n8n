# CRIE Deployment Guide

_Deliverable: §204 / §407. Sprint 10 (Production Hardening), v1.0.0._
_Authoritative spec: CRIE Enterprise Specification v1.1.1. Reconciliations R-01…R-18._

This guide describes how to deploy CRIE (Compliance Reasoning & Intelligence
Engine) to a target environment. The architecture is **frozen** and
**provider-agnostic**: every external service (LLM/embedding provider, OCR, BI,
datastore) is reached through the Provider Adapter layer, and this guide never
wires a specific provider into a workflow, prompt, SQL, or code node.

## 1. Topology

CRIE runs on four substrate components. Two deployment shapes are supported and
are interchangeable without any architectural change:

Self-hosted reference (this repo's `deployment/docker-compose/`): PostgreSQL 15
with pgvector, Redis (n8n queue backend), n8n main, and one or more n8n workers.
Managed: managed Supabase (PostgreSQL + pgvector) plus managed n8n; point the
n8n environment at the managed endpoints and skip the bundled `postgres`/`redis`
services.

The database schema is identical in both shapes — it is defined solely by the
ordered migrations in `database/migrations/` (§217/§239), never by ad-hoc SQL.

## 2. Prerequisites

A PostgreSQL 15+ instance with the `vector` (pgvector) extension available; an
n8n instance capable of **Queue Mode** (R-18); a Redis instance if self-hosting
queue mode; and the secrets listed in `.env.example`
(`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `OPENAI_API_KEY`, `AZURE_ENDPOINT`,
`AZURE_KEY`, `N8N_ENCRYPTION_KEY`). A BI platform capable of consuming Supabase
read-only views (R-17) is required for the Administration and benchmark
dashboards; n8n produces data, not UI.

Secrets are supplied per environment and never committed (§682). Copy
`.env.example` to `.env` and fill in real values.

## 3. Order of operations

Deployment follows the §200 pipeline. Each step is a gate; stop on first
failure.

1. **Stand up the substrate.** Self-hosted:
   `docker compose -f deployment/docker-compose/docker-compose.yml -f deployment/development/docker-compose.dev.yml up -d`
   (use `deployment/production/docker-compose.prod.yml` for production). Managed:
   provision Supabase + n8n and set the environment accordingly.
2. **Apply migrations (§217/§239).**
   `DATABASE_URL=… bash deployment/scripts/apply_migrations.sh` — runs
   `0001`…`0028` in order and stops on the first failure. All migrations are
   additive and reversible; `rollback_migrations.sh` reverses them.
3. **Validate + seed configuration (R-08/R-14/§327).**
   `DATABASE_URL=… bash deployment/scripts/seed_config.sh` — runs startup
   validation first (refuses to proceed if configuration is invalid) then syncs
   the authored `configuration/*.yaml` into the `configuration.*` runtime tables.
   Editing behavior means editing YAML and re-running this step; nothing is
   authored directly in the tables (§627).
4. **Build the vector index.** `python3 scripts/setup/apply_vector_index.py`
   (HNSW over `vector(1536)`, R-09).
5. **Import workflows (§623/§634).**
   `bash deployment/scripts/import_workflows.sh` (or the n8n CLI inside the
   container). Then in n8n: bind provider credentials (never stored in the JSON),
   and activate the Startup Validation utility (UT-007) and the scheduled
   dispatcher/telemetry/notification workflows.
6. **Smoke test (§200).**
   `DATABASE_URL=… N8N_HEALTH_URL=… bash deployment/scripts/smoke_test.sh`.
7. **Promote to production** only after the §406 gate is satisfied (Section 6).

The single ops entrypoint wraps all of the above:
`bash deployment/scripts/entrypoint.sh <migrate|seed|validate|smoke|gate|benchmark>`.

## 4. CI/CD (§200)

`.github/workflows/ci.yml` implements the §200 pipeline: Static Validation →
Workflow Validation → SQL Migration Validation → Unit Tests → Integration Tests
→ Benchmark Suite → Deploy Development → Deploy Production. The pipeline stops if
any stage fails. Deploy-development runs on `main`; deploy-production runs on a
`v*` tag and is gated on a protected `production` environment (manual approval),
which is where the §406 operational sign-offs are recorded.

## 5. Queue mode, checkpoints, circuit breaker (R-18 / §369–§384)

These behaviors are grounded on n8n-native mechanisms (R-18) and are verified in
the target deployment (S10-7): queue semantics via a status-column dispatcher
plus n8n queue-mode workers; checkpoints via the `processing_history` table
(resume from last completed stage on failure); circuit breaker via provider
health state in `health_checks` (fail fast while `Open`, scheduled recovery
test). Worker scaling is horizontal: `docker compose up --scale n8n-worker=N`
(§382). See the Operations Guide for verification procedures.

## 6. Production readiness gate (§406)

Do not deploy to production unless every §406 item holds: all benchmark targets
met; no Critical or High defects; UAT approved (§404); documentation complete;
backup tested; recovery tested; monitoring operational; cost tracking
operational. The build-environment status of these items is reported in the
Production Readiness Report; the operational items (UAT sign-off, backup/recovery
drills, live monitoring) are confirmed in the target environment and recorded on
the protected `production` deployment approval.

## 7. Rollback

To reverse the additive tail without touching the base schema (e.g. undo Sprint
9's `0027`–`0028`): `DATABASE_URL=… bash deployment/scripts/rollback_migrations.sh 0027`.
To reverse everything: run with no argument. Prompt registry and workflow JSON
are versioned in Git; configuration is re-seedable from YAML.
