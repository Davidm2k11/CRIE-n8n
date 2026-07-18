# CRIE — Compliance Reasoning & Intelligence Engine

All Rights Reserved, Copyright (c) 2026 Dawod Manasra. Unauthorized copying,
modification, distribution, or commercial use is prohibited without written
permission.

**Version:** v1.0.0 — production release. Authoritative specification:
CRIE Enterprise Specification v1.1.1 (frozen; reconciliations R-01…R-18).

CRIE is an enterprise RAG platform for compliance reasoning and knowledge
intelligence, built on n8n (workflow orchestration), Supabase/PostgreSQL with
pgvector, Azure Document Intelligence (OCR), and configurable, provider-agnostic
LLM/embedding adapters. Administration and benchmark dashboards are delivered as
read-only `admin.*` Supabase views surfaced by an external BI tool (R-17); n8n
produces data, not UI.

## Repository layout (§619–635)

- `configuration/` — authored YAML, the source of truth for all adjustable
  behavior (R-08); synced into `configuration.*` tables, never authored in-table.
- `database/` — ordered, additive migrations `0001…0028` with matching rollbacks
  (§217/§239), seeds, and ER diagram.
- `workflows/` — master workflows WF-001…WF-005 + UT-007 (`master/`,
  `utilities/`) and module logic + sub-workflows (`shared/`).
- `prompts/` — frozen catalog PR-001…PR-008 (R-04) and the registry.
- `schemas/` — canonical JSON/YAML contracts (Context Package, Compliance Result,
  Citation, Proposal Package, and operational schemas).
- `scripts/` — setup, benchmark, and repository tooling.
- `tests/` — acceptance suites; `tests/run_all.py` is the unified gate.
- `benchmark/` — labeled dataset and retained reports (§631).
- `deployment/` — Docker, Docker Compose, Supabase/n8n assets, and idempotent
  deployment scripts.
- `docs/` — architecture, deployment, operations, API, governance, and
  implementation documentation.

## Quick start

```bash
# 1. configure secrets
cp .env.example .env            # fill in real values (never commit .env)

# 2. stand up the reference substrate (self-hosted)
docker compose -f deployment/docker-compose/docker-compose.yml \
               -f deployment/development/docker-compose.dev.yml up -d

# 3. apply schema, validate + seed config, build the vector index
DATABASE_URL=... bash deployment/scripts/apply_migrations.sh
DATABASE_URL=... bash deployment/scripts/seed_config.sh
python3 scripts/setup/apply_vector_index.py

# 4. import workflows into n8n, then smoke-test
bash deployment/scripts/import_workflows.sh
DATABASE_URL=... N8N_HEALTH_URL=... bash deployment/scripts/smoke_test.sh
```

See `docs/deployment/Deployment_Guide.md` for the full procedure (including
managed Supabase / managed n8n) and the §406 production readiness gate.

## Run the acceptance gate

```bash
python3 tests/run_all.py        # 9 suites, 265 tests
```

Requires Python 3.12 (+ PyYAML) and Node.js 22 for the JS suites.

## Documentation

Deployment (`docs/deployment/`), Operations (`docs/operations/`), API
(`docs/api/`), and governance reports — Repository Audit, Security Review,
Production Readiness — under `docs/governance/`. Project status is tracked in
`PROJECT_STATUS.md`; release history in `CHANGELOG.md`.

## License

All Rights Reserved. See `LICENSE`.
