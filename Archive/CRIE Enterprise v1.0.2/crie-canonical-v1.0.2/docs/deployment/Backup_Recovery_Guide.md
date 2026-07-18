# CRIE Backup & Recovery Guide

_Deliverable: S10-5 / S10-6 (§201, §202, §349, §350). Sprint 10, v1.0.0._
_Authoritative spec: CRIE Enterprise Specification v1.1.1._

Backup policy, recovery procedures, and drill instructions for a running CRIE
deployment. These are the operational counterparts to the §406/§616 "backup
tested / restore tested" gate items, which are confirmed in the target
environment.

## 1. Backup policy (§201 / §349)

| Asset | Strategy | Cadence |
|---|---|---|
| Repository (knowledge, evidence, citations) | Logical + physical database backup | Daily |
| Configuration | Database backup **and** authored `configuration/*.yaml` in Git | Daily / on change |
| Prompt Registry | Git version control (`prompts/`) | On change |
| Workflow JSON | Git version control (`workflows/`) | On change |
| Database (all schemas) | Point-in-Time Recovery (PITR) | Continuous |

The authored YAML and the workflow/prompt JSON are the sources of truth and live
in Git, so configuration, prompts, and workflows are recoverable independently of
the database. The database itself (knowledge, embeddings, audit, monitoring)
relies on PITR plus daily backups.

Audit records are immutable and retained a minimum of 365 days (§344/§345);
backups must preserve them for at least the retention window.

## 2. Taking backups

**Managed Supabase:** enable daily backups and PITR in the project settings;
verify the retention window covers the §345 audit minimum.

**Self-hosted PostgreSQL:** schedule `pg_dump` (logical) daily and enable WAL
archiving for PITR. Example logical backup:

```bash
pg_dump "$DATABASE_URL" --format=custom --file="crie_$(date +%F).dump"
```

Configuration, prompts, and workflows require no separate database backup — they
are restored from Git and re-seeded (Section 3).

## 3. Recovery procedures

### 3.1 Repository failure (§202)

```
Restore Backup → Rebuild Embeddings → Validate Repository → Resume Processing
```

1. Restore the most recent database backup (or PITR to just before the
   incident).
2. Rebuild embeddings for any affected knowledge units
   (`scripts/setup/apply_vector_index.py` for the index;
   `rebuildEmbeddings` repository API for content, which enforces the
   `vector(1536)` lock-in, R-09).
3. Validate the repository (certification and health checks).
4. Resume processing from the dispatcher; in-flight documents resume from their
   last checkpoint (`processing_history`).

### 3.2 Workflow failure (§202)

```
Retry → Resume from Checkpoint → Human Review
```

Recoverable failures retry automatically (§383). If retry is exhausted, the
document resumes from its last completed stage; if it still cannot proceed it is
routed to human review (§154/§202).

### 3.3 Full disaster recovery (§350)

```
Restore Database → Validate Repository → Rebuild Embeddings → Validate Retrieval → Resume Processing
```

1. Provision a fresh substrate (Deployment Guide §1–§3).
2. Restore the database from backup/PITR.
3. Re-apply any migrations newer than the backup
   (`deployment/scripts/apply_migrations.sh` is idempotent and stops on failure).
4. Re-seed configuration from Git (`deployment/scripts/seed_config.sh`).
5. Re-import workflows and re-bind provider credentials
   (`deployment/scripts/import_workflows.sh`).
6. Validate the repository and retrieval, then resume processing.
7. Run the smoke test (`deployment/scripts/smoke_test.sh`) and the acceptance
   gate (`tests/run_all.py`).

## 4. Drills (§406 "backup tested / recovery tested")

Backup and recovery are not "done" until drilled in the target environment.
Recommended cadence: quarterly, plus after any schema-affecting change.

**Backup drill.** Take a fresh backup; confirm it completes and that audit
records within the retention window are present.

**Restore drill.** Restore the backup into an isolated environment; run the
smoke test and the acceptance gate against it; confirm the repository validates
and retrieval returns certified-only results. Record the drill outcome against
the §406 gate.

Until both drills pass in the target environment, the §406 gate items "Backup
tested" and "Recovery tested" remain Pending and production deployment is
withheld.
