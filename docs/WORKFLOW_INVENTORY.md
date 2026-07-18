# CRIE v1.0 — Workflow Inventory

Which workflow records are **ACTIVE** (part of v1.0) and which imported copies
should be **ARCHIVED/DELETED** so the parent→child bindings cannot drift.

## ACTIVE — the v1.0 set (import these, bind WF-001 to these)

| Workflow | Version | Role | Notes |
|---|---|---|---|
| **WF-001 Knowledge Ingestion** | v0.10.1 | Master ingestion pipeline | Contains the taxonomy pre-flight, Register-Document `ON CONFLICT` fix, and the documentId guard. **After import, re-bind the `SW-008 LLM Knowledge` Execute Workflow node to the ACTIVE SW-008 by ID** (see below). |
| **SW-005 Azure OCR** | current | OCR + normalize (paragraph-first) | Re-bind the Azure header credential after import. |
| **SW-007 Metadata** | trigger-fixed | Document metadata (single call) | `inputSource:"passthrough"` fix applied. |
| **SW-008 LLM Knowledge** | **v3.5.0** | Batched knowledge extraction | The record WF-001 MUST call. Contains `build-request()` materialization + fail-fast and the `Return to WF-001` terminal. |
| **SW-013 Embeddings** | trigger-fixed | Embedding generation | `inputSource:"passthrough"` fix applied. |
| **SW-014 Repository Writer** | **v1.1.0** | Single-transaction persist | Contains the `uid()`/`fk()` UUID fix (no more `id=''`). |

Other sub-workflows referenced by WF-001 (SW-001/002/003/004/006/009/010/011/012/015)
are unchanged from their last-good state and are part of the ACTIVE set.

## CRITICAL — the parent→child binding

WF-001's `SW-008 LLM Knowledge` node (`n8n-nodes-base.executeWorkflow` v1.2) is
configured `mode:"list"` with an **empty `workflowId.value`** in the shipped JSON.
Every import mints a **new** workflow ID, so a `list`/cached-name binding can
resolve to a **stale SW-008**. This caused the parent to receive its own input
instead of the child's output.

**Required after import:**
1. Open the ACTIVE SW-008 v3.5.0; copy its `/workflow/<ID>`.
2. In WF-001, re-select it on the `SW-008 LLM Knowledge` node and **save**.
3. Prefer pinning by ID: set `workflowId.mode:"id"`, `value:"<the id>"` — a
   literal-ID binding cannot drift to a same-named record.
4. Repeat the re-bind check for **every** Execute Workflow node in WF-001 (each
   import re-IDs its target).

### Frozen contract property — Wait for Sub-Workflow Completion

The `SW-008 LLM Knowledge` node has **`options.waitForSubWorkflow: true`** set
explicitly in the WF-001 JSON (v0.10.2). This property **is serialized** in the
workflow (n8n `executeWorkflow` typeVersion 1.2), so it travels with the import
and is **part of the frozen contract, not a manual deployment step**.

- Do **not** rely on the implicit default (`options: {}`): it is now stated
  explicitly so the behaviour is unambiguous across imports and n8n versions.
- Do **not** toggle this off. With it off, WF-001 continues before SW-008 returns
  and `knowledge.knowledgeUnits` is never received → false HUMAN_REVIEW.
- If a future re-export shows `options: {}` on this node, re-apply
  `waitForSubWorkflow: true` before freezing.

## ARCHIVE / DELETE — stale imported copies

During bring-up, many SW-008 iterations were imported, each minting a new ID.
Any of these still resident in n8n is a binding hazard.

| Pattern | Action |
|---|---|
| SW-008 **v1.x / v2.x** (terminal node `Shape Result`, pre-batching) | **Delete.** Wrong output contract; a stale bind here returns the input payload. |
| SW-008 **v3.0.0 – v3.4.x** (terminal `merge()`, no `Return to WF-001`) | **Delete.** Superseded by v3.5.0. |
| Any duplicate SW-005/007/013/014 from repeated imports | **Delete** all but the ACTIVE record. |
| Older WF-001 imports (< v0.10.1) | **Delete.** |

**Rename the survivors** to include the version (e.g. `SW-008 LLM Knowledge v3.5.0`)
so the list picker is unambiguous.

## Post-import verification

- WF-001 `SW-008 LLM Knowledge` node shows a **non-empty** `workflowId.value` that
  matches the ACTIVE SW-008 v3.5.0 ID.
- A test ingestion returns `knowledge.knowledgeUnits` to WF-001 (the `LLM ok?`
  branch passes, no false HUMAN_REVIEW).
- Exactly one record per workflow name resolves in the picker.
