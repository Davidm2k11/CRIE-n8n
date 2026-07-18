# CRIE v0.4.0 — Sprint 3: Knowledge Ingestion

**Tag:** `v0.4.0` · **Depends on:** `v0.3.0` (Sprint 2 — Database)

## Added
- **WF-001 Knowledge Ingestion** master workflow (§154, §210–216) — importable
  n8n JSON + versioned orchestrator module.
- **Module-13 sub-workflows SW-001 … SW-015** (R-01): correlation ID, SHA256,
  duplicate detection, register, Azure OCR (retry ×3), OCR validation, metadata
  extraction (PR-002), knowledge extraction (PR-001), evidence, citation,
  knowledge validator, chunk builder, embedding (1536), repository writer
  (single transaction), certification.
- **Prompt Registry bodies PR-001 / PR-002** — loaded at runtime, never embedded.
- **processing_history checkpoints** at every stage (R-18).
- Acceptance + unit test suite (17 tests, all passing), example input/output,
  module documentation.

## Honors
R-01 (Module-13 IDs), R-05 (16-value category enum), R-06 (citations key on
evidence_id + document_id), R-09 (vector(1536)), R-13 (chunk/embedding owned by
Repository), R-18 (checkpoints); Principle 2 (deterministic before AI),
Principle 7 (no hardcoded config), §608 (no embedded prompts/secrets, Repository
never bypassed).

## Failure policy (§154)
Duplicate → Stop · OCR → Retry ×3 → Human Review · Extraction → Human Review ·
Repository → Rollback.

## Exit gate
One uploaded document becomes certified knowledge. **Met.**

## Notes
- Live Supabase application is deferred to the infrastructure integration stage
  (accepted no-live-datastore-in-build risk); the pipeline is exercised
  end-to-end against in-memory doubles that call the real workflow logic.
- No future-sprint artifacts included (strict sprint isolation).
