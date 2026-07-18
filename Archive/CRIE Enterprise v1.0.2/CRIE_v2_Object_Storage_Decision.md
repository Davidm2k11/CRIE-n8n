# CRIE v2 Architecture Decision — Object Storage (gated)

## Decision
Object storage (per `CRIE_Document_Lifecycle_Object_Storage_Standard.md`) is adopted as the
**platform standard for CRIE v2**. The original file is stored exactly once; workflows pass only
`{ documentId, sha256, storageKey, correlationId }`; SW-005 obtains the file via signed URL
(`urlSource`) or download-then-`base64Source` fallback.

## Status: APPROVED IN PRINCIPLE, IMPLEMENTATION GATED

Implementation of the object-storage migration MUST NOT begin until BOTH gates pass:

- [ ] **Gate 1 — End-to-end run of the CURRENT pipeline.** WF-001 (v0.7.7 binary path) completes
      at least one successful end-to-end execution: Download → SHA-256 → dup-check → register →
      SW-005 OCR → SW-007/008 → SW-009-012 → SW-013 embeddings → SW-014 write → SW-015 certify,
      producing a certified document with populated repository + embeddings.
      - Depends on the binary-boundary probe (Appendix A) resolving the SW-005 binary access.

- [ ] **Gate 2 — Azure `urlSource` integration test.** The `curl` test confirms Azure Document
      Intelligence successfully fetches a Supabase signed URL for this infrastructure
      (202 Accepted + Operation-Location), OR the download-then-base64Source fallback is confirmed
      as the SW-005 variant.

## Sequencing rationale
Do not rebuild ingestion on an object-storage foundation until the current pipeline is proven
working end-to-end (so we have a known-good baseline to migrate FROM) and the urlSource fetch is
validated on real infrastructure (so the v2 SW-005 design rests on a tested capability, not an
assumption). This avoids migrating onto two simultaneously-unverified foundations.

## What remains valid regardless
- `CRIE_Workflow_Engineering_Guidelines.md` — applies to v1 and v2.
- `CRIE_Document_Lifecycle_Object_Storage_Standard.md` — the v2 design, unchanged; migration
  section (§11) executes only after both gates pass.
- WF-005 scaffold ID corrections (SW-018/019/UT-000/UT-006) — still deferred, independent of this.

## Current pipeline state (v1, the baseline to prove)
- WF-001 v0.7.7: state propagation complete; checkpoints off-stream; SW-004 idempotent dev-bypass;
  binary re-attach node present; SW triggers v1.1 passThrough.
- SW-005/007/008/013/014 v1.3.0: enrichment pattern; jsonb settings fix; passThrough triggers.
- Open before Gate 1: binary-boundary probe result → confirms or fixes SW-005 binary access.
