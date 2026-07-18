# Configuration Guide

CRIE configuration is **authored as YAML** under `configuration/` — the single
source of truth (R-08, §627) — and loaded into the `configuration.*` runtime
cache tables (§228) by the seed step in Sprint 2. Values are edited in YAML and
synced; they are never authored directly in the tables and never hardcoded in
workflows (Principle 7, §621).

## Files (§627)

| File | Covers | Spec |
|------|--------|------|
| `providers.yaml` | OCR, LLM, embedding, storage provider settings | §302–304, §320 |
| `repository.yaml` | Certification, versioning, transaction timeout | §307 |
| `retrieval.yaml` | topK, similarity, reranker gate, ranking weights, expansion | §305, §462, §454–455 |
| `reasoning.yaml` | Confidence thresholds, human-review triggers | §483–484, §91 |
| `monitoring.yaml` | Telemetry, cost/perf tracking, health interval | §308 |
| `feature_flags.yaml` | Feature toggles (default false) | §312 |
| `logging.yaml` | Log level, retention, destination | §309 |
| `storage.yaml` | Buckets, retention | §310 |
| `security.yaml` | Allowed secret locations, RLS, audit, injection protection | §322, §235, §344, §340–342 |
| `benchmark.yaml` | Benchmark datasets and retention | §631 |

## Reading configuration

Every module requests values from the registry, e.g. `config.retrieval.topK`.
Hardcoding (`const TOP_K = 10`) is prohibited (§12).

## Secrets

Secrets are **never** in configuration YAML. They live only in environment
variables / n8n credentials / cloud secret managers (§322). See `.env.example`
and the environment table in the root `README.md` (§169, §682). Only adapter
nodes access secrets; business nodes never do (§324).

## Environment variables (§314)

| Variable | Required |
|----------|----------|
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Yes |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY` | Yes |
| `OPENAI_API_KEY` | Yes |
| `ANTHROPIC_API_KEY` | If LLM provider = anthropic |
| `GOOGLE_DRIVE_CREDENTIALS` | For Google Drive storage adapter |
| `LOG_LEVEL`, `ENVIRONMENT` | Recommended |

## Validation (§327)

Run the Startup Validation core:

```bash
python3 scripts/setup/validate_configuration.py            # config-only
python3 scripts/setup/validate_configuration.py --check-env # + required secrets
```

Checks: required values exist, embedding dimension = 1536 (R-09), valid log
level, structured logging on, feature flags boolean, reranker gate, ranking
weights sum to 1.0, endpoint URL validity, and (with `--check-env`) required
secret presence. Failure ⇒ health `Critical` + alert + execution blocked (R-14).

## Config-driven database behavior (Sprint 2)

These are adjusted in YAML and applied by re-running the seed / index scripts —
no SQL or workflow edits. All are validated by the startup checks (UT-007).

| Setting | File | Applied by | Spec |
|---------|------|-----------|------|
| Vector index type/metric/params | `providers.yaml` → `embedding.vectorIndex` | `scripts/setup/apply_vector_index.py` | §227 |
| Authority sources & scores | `retrieval.yaml` → `authoritySources` | `scripts/setup/seed_configuration.py` | §439, R-16 |
| Synonyms / acronyms | `database/seeds/dictionaries.yaml` | seed script | §444–445 |
| Knowledge categories (frozen 16) | `database/seeds/knowledge_categories.yaml` | seed script + `0018` CHECK | §438, R-05 |
| All domain config values | `configuration/*.yaml` | seed script → `configuration.configuration` | R-08 |
| RLS on/off | `security.yaml` → `rowLevelSecurity` | `0014` | §235 |

Workflow to change behavior:

```bash
# 1. edit the relevant YAML
# 2. re-sync the runtime cache
python3 scripts/setup/seed_configuration.py --apply
# 3. (if you changed embedding.vectorIndex)
python3 scripts/setup/apply_vector_index.py --apply
# 4. re-run startup validation
python3 scripts/setup/validate_configuration.py
```

## Changing an embedding dimension (R-09)

`embedding.dimensions` is configurable but fixed at **1536** for v1. Changing it
is a schema migration (new vector column type) plus a full re-embed (§523), not a
runtime toggle. Providers may be switched freely among 1536-dimension models via
config alone.

## Environment profiles (§315, §325)

Development / Testing / UAT / Production may each define different configuration
values; **workflow logic remains identical** across profiles.
