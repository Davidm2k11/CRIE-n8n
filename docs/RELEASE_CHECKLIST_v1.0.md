# CRIE v1.0 — Release Checklist (before WF-002 Retrieval)

Freeze gate for the current working implementation. Complete every MUST item
before starting WF-002.

## 1. Database

- [ ] Migrations `0001–0028` replay cleanly on an **empty** PostgreSQL 16 in order
      (ideally in CI against an ephemeral instance — see §6).
- [ ] `chk_knowledge_units_category` holds exactly the **§438 16 values**; the seed
      table `configuration.knowledge_categories` matches it (taxonomy pre-flight →
      `taxonomyOk = true`).
- [ ] `repository.embeddings.embedding` is `vector(1536)` (R-09).
- [ ] RLS present on `repository.documents`; n8n role is `service_role`/owner and
      can INSERT **and** UPDATE (empirically proven by the pipeline).

## 2. Prompts

- [ ] **PR-001 v1.2** applied; `ORDER BY version DESC LIMIT 1` selects **1.2**.
- [ ] The loaded PR-001 contains the `{{ocr}}` placeholder (built via `chr()`), the
      LANGUAGE-preservation block, and all 16 §438 categories; contains no literal
      `undefined`.
- [ ] All prompt SQL is dollar-quoted and `{{`-free (n8n-interpolation safe).

## 3. Workflows

- [ ] The **ACTIVE** set imported (WF-001 v0.10.1; SW-005; SW-007; SW-008 v3.5.0;
      SW-013; SW-014 v1.1.0; plus unchanged SW-001/002/003/004/006/009/010/011/012/015).
- [ ] **Every** Execute Workflow node in WF-001 re-bound to the freshly-imported
      child; `SW-008 LLM Knowledge` pinned **by ID** to v3.5.0.
- [ ] Azure credential re-bound on SW-005; OpenAI credential on SW-008/SW-013.
- [ ] All **stale** SW-008/SW-005/SW-007/SW-013/SW-014 and old WF-001 copies
      **deleted**; survivors renamed with their version.
- [ ] Exactly one record resolves per workflow name in the picker.

## 4. End-to-end validation

- [ ] **English** document ingests to `PROCESSED`; knowledge units written; no false
      HUMAN_REVIEW; `knowledge.knowledgeUnits` returns to WF-001.
- [ ] **Arabic** document ingests; KU **statements remain Arabic** (v1.2).
- [ ] A large (≈60-page) document completes without heap OOM under the documented
      `6144` / concurrency-1 config.
- [ ] SW-014 commits the single transaction with **no** `uuid: ""` error.
- [ ] Register-Document returns a real UUID on a brand-new document (no null).

## 5. Configuration & ops

- [ ] Worker env: `--max-old-space-size=6144`, `QUEUE_WORKER_CONCURRENCY=1`,
      queue mode, filesystem binary.
- [ ] BI layer reads `admin.*` views.
- [ ] **Orphan-document sweep** scheduled (recommended MUST for production; a worker
      crash otherwise leaves a document silently `PENDING`). Artifacts delivered
      post-v1.0: migration `0029` + `SW-016 Orphan Sweep`. Remaining env action —
      apply `0029`, import/bind/activate `SW-016`, set the `CRIE_ORPHAN_SWEEP_*` vars.

## 6. Regression guards (recommended before WF-002)

- [ ] CI: ephemeral-Postgres **migration replay** (catches forward-reference defects
      invisible to text tests).
- [ ] CI: `pgcheck.py` over all prompt/repair SQL (adjacent-literal + `{{` guard).
- [ ] CI: `validate_workflows.py` over all workflow JSON (node-ref, trigger
      passthrough, prompt-ref, IF-schema, 3VL-INSERT, taxonomy-enum checks).

## 7. Freeze

- [ ] Tag the repository **`v1.0`** (migrations 0001–0028; PR-001 v1.2; the ACTIVE
      workflow set).
- [ ] `SRD_CHANGES_SINCE_SPEC.md` reviewed and accepted by the Architecture Owner.
- [ ] Deferred items explicitly logged as post-v1.0 (per-batch refactor, adaptive
      density, §406 sign-offs, WF-002).

## 8. Sign-off

- [ ] Architecture Owner sign-off recorded.
- [ ] WF-002 Retrieval may begin **only** after all MUST items above are checked.

---

### MUST (block the freeze) vs SHOULD (strongly recommended)

**MUST:** all of §1–§4, worker config in §5, repository tag in §7, sign-off in §8.
**SHOULD:** orphan sweep (MUST for production traffic), all of §6, the full §7 review.
