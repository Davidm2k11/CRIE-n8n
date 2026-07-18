# CRIE — Project Context

> **Stable document.** This describes *what CRIE is* and *the architecture it is
> built toward*. It should change rarely. For the current state of work see
> [`PROJECT_STATUS.md`](PROJECT_STATUS.md); for the frozen release see
> [`CANONICAL_BASELINE.md`](CANONICAL_BASELINE.md).

## Purpose

CRIE is a **compliance knowledge platform**. It ingests source documents,
extracts governed, auditable **Knowledge Units** from them, embeds those units
for semantic retrieval, and persists everything into a governed relational
repository that downstream reasoning and reporting can build on.

The platform is designed so that every knowledge unit is traceable back to its
evidence and citation, classified against a fixed taxonomy, and attributed to a
known authority source — the requirements of a system that produces defensible
compliance output rather than best-effort summaries.

## Conceptual architecture

CRIE is an **orchestration-over-database** system, not a bespoke application:

- **Orchestration layer — n8n** (Queue Mode, filesystem binary storage). Business
  logic lives in n8n workflows and sub-workflows. A master workflow drives the
  pipeline and calls single-responsibility sub-workflows via `executeWorkflow`.
- **Data layer — PostgreSQL 16** (Supabase), with `pgvector` for embeddings and
  `uuid-ossp` for identifiers. The database is the system of record and enforces
  the platform's invariants through constraints, RLS, and append-only audit
  triggers rather than trusting the orchestration layer to behave.
- **External services** — Azure Document Intelligence for OCR, and OpenAI
  (GPT-4o) for metadata extraction, knowledge extraction, and embeddings.

The database is organised into schemas by concern: `repository` (documents,
knowledge units, evidence, citations, retrieval chunks, embeddings),
`configuration` (prompt registry, taxonomy, providers), `monitoring` (processing
history), `audit` (append-only audit trail), and `admin` (dashboard/BI views).

## The end-to-end vision (workflow families)

CRIE is planned as a pipeline of workflow families. Only the first is
implemented today; the rest exist as skeletons and define the roadmap. See
[`PROJECT_STATUS.md`](PROJECT_STATUS.md) for what is actually built.

| Family | Purpose | State |
|---|---|---|
| **WF-001 Knowledge Ingestion** | OCR → metadata → batched knowledge extraction → embeddings → single-transaction persist | **Implemented (v1.0, frozen)** |
| **WF-002 Enterprise Retrieval** | Semantic + structured retrieval over the repository | Roadmap skeleton |
| **WF-003 Enterprise Reasoning** | Compliance reasoning over retrieved knowledge | Roadmap skeleton |
| **WF-004 Output Generation** | Produce the compliance result / report artifacts | Roadmap skeleton |
| **WF-005 Administration** | Scheduled operational/administration tasks | Roadmap skeleton |

## Frozen invariants

These are architectural commitments. They are enforced in the schema and treated
as canonical; changing any of them is a deliberate re-architecture decision, not
a routine change. Rationale is recorded in
[`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md).

- **Category taxonomy (R-05):** the §438 **16-value** knowledge-category enum,
  enforced by the `chk_knowledge_units_category` CHECK constraint and mirrored in
  `configuration.knowledge_categories`.
- **Embeddings (R-09):** `vector(1536)`.
- **Additive-only migrations:** the DDL chain is append-only; corrections ship as
  new migrations, never edits to existing ones.
- **Single Compliance Result contract** and a **frozen 8-prompt catalogue**
  (PR-001 … PR-008).
- **9-source authority model (R-16):** platform-computed confidence and
  deterministic compliance-level derivation.
- **YAML-authored configuration as source of truth (R-08).**

## Design principles

- **The database enforces correctness.** Invariants live in constraints, RLS, and
  triggers so no workflow can violate them.
- **Sub-workflows are single-responsibility** and communicate through an explicit
  I/O contract.
- **Determinism where it matters** — taxonomy, confidence, and compliance-level
  derivation are computed, not model-guessed.
- **Baselines are frozen and reproducible** — a tagged release reproduces from an
  empty database via the migration chain.
