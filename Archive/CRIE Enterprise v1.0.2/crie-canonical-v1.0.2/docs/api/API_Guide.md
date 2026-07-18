# CRIE API Guide

_Deliverable: §204 / §407 (API_Guide / API Documentation). Sprint 10, v1.0.0._
_Authoritative spec: CRIE Enterprise Specification v1.1.1._

CRIE exposes two API surfaces: the **Repository API** (the only sanctioned path
for repository access, §339) and the **workflow contracts** (the versioned JSON
that flows between workflow boundaries). Direct SQL from workflows is prohibited
except through the designated repository components (§339).

## 1. Repository API (§514–§531)

`workflows/shared/repository_api.js` exposes `createRepositoryApi(deps, config)`.
All methods return a structured result and enforce the repository rules: only
**certified**, non-archived knowledge is retrievable (§338); archive never
deletes and remains recoverable (§530/§531); embedding rebuilds enforce the
`vector(1536)` lock-in (R-09).

| Method | Purpose | Key rules |
|---|---|---|
| `createDocument(bundle)` | Persist a document + derived objects | Transactional; no duplicate objects (§371) |
| `updateDocument(documentId, changes)` | Apply changes to a document | Incremental; affects only changed objects (§380) |
| `archiveDocument(documentId)` | Archive a document | Never deletes; stays recoverable (§530/§531) |
| `getKnowledgeUnit(id)` | Fetch a knowledge unit | Certified-only (§518) |
| `searchMetadata(query)` | Metadata search | Filters precede retrieval (§457) |
| `searchKnowledge(query)` | Knowledge search | Certified-only results (§338) |
| `rebuildEmbeddings(scope)` | Rebuild embeddings | Requires a reserved reason; enforces 1536 dims (§523/R-09) |
| `repositoryStatistics()` | Aggregate stats + health score | Read-only |
| `repositoryHealth()` | Health snapshot | Read-only |

Example input/output: `examples/repository/api_example_input.json`,
`examples/repository/api_example_output.json`.

## 2. Workflow contracts (§291/§295/§452/§481)

Canonical, versioned JSON contracts define each workflow boundary. They live in
`schemas/contracts/` and are the interface between workflows:

- **Context Package** (`context_package.contract.json`) — retrieval → reasoning
  boundary; isolated per request (§342).
- **Compliance Result** (`compliance_result.contract.json`, §295/R-03) —
  reasoning output; consumed by output generation.
- **Citation** (`citation.contract.json`, §291/R-06) — re-linkable citation with
  `evidenceId` + `documentId`.
- **Proposal Package** (`proposal_package.contract.json`) — output-generation
  package.
- Operational schemas: `structured_log`, `telemetry`, `health_status`,
  `execution_summary`, `adapter_error`, `workflow_error`.

Every Compliance Result supports full reverse tracing (§347/§348):
Requirement → Compliance Result → Evidence → Knowledge Unit → Citation →
Document.

## 3. Master workflows (§623)

| ID | Name | Role |
|---|---|---|
| WF-001 | Knowledge Ingestion | Upload → OCR → knowledge → embeddings → repository |
| WF-002 | Enterprise Retrieval | Hybrid search + context building |
| WF-003 | Enterprise Reasoning | Compliance generation with citations |
| WF-004 | Output Generation | Proposal package + exports |
| WF-005 | Administration | Scheduled ops, dashboards data, alerts |
| UT-007 | Startup Validation | R-14 config/secret/provider validation |

Sub-workflow IDs SW-001…SW-028 are referenced per R-01; SW-026–028 ship as
standalone n8n JSON, the remainder are realized as module code.

## 4. Authentication & access (§334–§339)

Phase 1 uses platform authentication only (no end-user auth); RBAC roles
(§336/§337) are defined for a future phase. Every external provider authenticates
(API key / OAuth / service account); no anonymous providers (§335). LLMs receive
only the Context Package, prompt, and variables — never raw PDFs, the whole
repository, keys, configuration, secrets, or internal logs (§340). Uploaded
document content is treated as data only and cannot modify the system prompt,
configuration, or workflow logic (§341).

## 5. AI-in-artifacts (Anthropic API)

Not part of the CRIE runtime. CRIE reaches LLM/embedding providers through the
Provider Adapter layer (provider-agnostic; OpenAI is the v1 default per §316–320)
and never embeds provider-specific calls in workflows, prompts, SQL, or code.
