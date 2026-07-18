# WF-001 — Knowledge Ingestion (Sprint 3)

**Version:** 0.4.0 · **Owner:** Dawod Manasra · **Spec:** CRIE Enterprise Specification v1.1 (frozen)

Converts an uploaded document into **certified enterprise knowledge**. Implements
the master workflow WF-001 (§154, §210–216) using the canonical Module-13
sub-workflows SW-001 … SW-015 (R-01).

## Pipeline (deterministic order, §154 / §210)

1. **Google Drive Trigger** — receive binary (§211).
2. **SW-001** Generate Correlation ID (§241).
3. **SW-002** Generate SHA256 (§242) — deterministic fingerprint.
4. **SW-003** Duplicate Detection (§243) — if the SHA256 exists → **Stop**.
5. **SW-004** Register Document / Passport (§244) → `Upload` checkpoint.
6. **SW-005** Azure OCR Adapter (§245) — retry ×3 exponential backoff.
7. **SW-006** OCR Validation (§246, §29) — Pass / Warning+log / Fail.
8. **SW-007** Metadata Extraction (§247, §30) — loads **PR-002**.
9. **SW-008** Knowledge Extraction (§248, §31) — loads **PR-001**; one fact = one KU.
10. **SW-009** Evidence Generator (§249, §32).
11. **SW-010** Citation Generator (§250) — citations key on `evidenceId` + `documentId` (**R-06**).
12. **SW-011** Knowledge Validator (§251, §34) — invalid KUs never enter the repository.
13. **SW-012** Semantic Chunk Builder (§252) — chunks validated KUs only, never raw OCR.
14. **SW-013** Embedding Generator (§253) — `vector(1536)` v1 default (**R-09**).
15. **SW-014** Repository Writer (§254) — single transaction; rollback on failure.
16. **SW-015** Repository Certification (§255) — all checks pass → **CERTIFIED**.

Every workflow follows Initialize → Validate → Execute → Verify → Persist → Log →
Return (§212) and ends with an Execution Summary (§216) consumed by Monitoring.

## Failure policy (§154)

| Failure | Action |
|---|---|
| Duplicate | Stop (no error; returns `DUPLICATE`) |
| OCR | Retry ×3 (SW-005); on final failure → document `HUMAN_REVIEW` |
| Extraction | → document `HUMAN_REVIEW` |
| Repository | Rollback (single transaction) |

## Checkpoints (R-18, §424, §372)

A `monitoring.processing_history` row (append-only) is written `PENDING` before
and `COMPLETED`/`FAILED` after each stage: `Upload`, `OCR`, `KnowledgeExtraction`,
`ChunkGeneration`, `Embeddings`, `Certification`.

## Prompts

PR-001 (Knowledge Extraction) and PR-002 (Metadata Extraction) are **loaded from
the Prompt Registry** at runtime (§175) and are never embedded in the workflow
(§608, §612). Bodies live in `prompts/`.

## Provider independence

OCR, LLM, embedding and DB access go through injected adapters (§316–320). The
same logic runs inside n8n Code nodes (wired to the Sprint-1 adapters) and under
Node with in-memory doubles for testing. The `.js` modules hold the logic per the
Code Node Policy (§168); the `.json` is the importable n8n workflow.

## Files

- `workflows/master/WF-001_Knowledge_Ingestion.js` — orchestrator.
- `workflows/master/WF-001_Knowledge_Ingestion.json` — importable n8n workflow.
- `workflows/shared/module13_ingestion.js` — SW-001 … SW-015.
- `prompts/knowledge_extraction/PR-001.yaml`, `prompts/metadata_extraction/PR-002.yaml`.
- `tests/acceptance.test.js`, `tests/fakes.js`.
- `examples/WF-001_example_input.json`, `examples/WF-001_example_output.json`.

## Running the tests

```
node tests/acceptance.test.js
```

## Acceptance (DoD)

**One uploaded document becomes certified knowledge.** Verified end-to-end by
`WF-001: one uploaded document becomes CERTIFIED knowledge (DoD)` plus 16
supporting tests (17/17 passing).

## Deferred to later sprints (not in Sprint 3)

- Live application against Supabase (infrastructure integration stage — accepted
  no-live-datastore risk).
- Repository hardening/versioning/APIs/health (Sprint 4).
- Retrieval, reasoning, output generation (Sprints 5–7).
No future-sprint artifacts are included here.
