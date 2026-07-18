# CRIE Document Lifecycle — Object Storage Platform Standard

**Status:** Design proposal for Architecture Owner sign-off. Supersedes binary-in-item (Design A) and base64-in-JSON (Design B) as the canonical approach.
**Principle:** The original uploaded file is stored exactly once in object storage. Workflows thereafter pass only a small reference tuple — never the binary.

The reference tuple carried between all nodes and across all Execute Workflow boundaries is:

```
{ documentId, sha256, storageKey, correlationId }
```

No `item.binary` on the main path. This eliminates the entire class of binary-propagation bugs (item replacement by Postgres/HTTP nodes, sub-workflow boundary marshalling, filesystem-pointer resolution) because there is no binary to lose — only a string reference.

---

## 1. Canonical capability check (verified)

- **Azure Document Intelligence v4.0 (2024-11-30) accepts `urlSource`.** The analyze endpoint takes a JSON body of either `{ "base64Source": "..." }` or `{ "urlSource": "https://..." }`. This is confirmed in the Azure REST reference. Therefore SW-005 can pass a **signed URL** to the original file and the bytes never enter n8n.
- **Supabase Storage supports time-limited signed URLs** (`createSignedUrl`) for private buckets, so the file stays private and Azure fetches it directly for a short window.

This makes the "SW-005 provides Azure a signed URL" path the primary design; a "download-then-base64Source" path is the fallback if signed-URL egress to Azure is disallowed by network policy.

---

## 2. Storage bucket layout

Single private bucket, environment-scoped:

```
crie-documents-{env}          # env ∈ {prod, staging, dev}
└── originals/
    └── {yyyy}/{mm}/{dd}/
        └── {documentId}/
            └── {sha256}.{ext}          # the original, stored exactly once
```

Rationale:
- **`originals/` prefix** reserves room for future sibling prefixes (`derived/`, `thumbnails/`, `redacted/`) without colliding.
- **Date partition `{yyyy}/{mm}/{dd}`** keeps object listings bounded and supports lifecycle rules by age.
- **`{documentId}/` folder** groups all artifacts for a document and makes per-document deletion (GDPR erasure, §-retention) a single prefix delete.
- **`{sha256}.{ext}` filename** makes the object self-verifying (name = content hash) and idempotent: the same file content always maps to the same object name within its document folder.

Private bucket only. No public read. Access via signed URLs or service-role key.

---

## 3. Naming convention (storageKey)

`storageKey` is the full object path within the bucket, stored verbatim in the DB:

```
originals/2026/07/11/{documentId}/{sha256}.pdf
```

Rules:
- Lowercase; date zero-padded; extension derived from validated MIME type (pdf, png, jpg, tiff…).
- `storageKey` is the single source of truth for locating the file. The bucket name is environment config, not part of the key, so the same key resolves across environments.
- Never encode secrets or PII in the key. `documentId` (UUID) and `sha256` are non-sensitive.

---

## 4. Schema additions (additive-only, per project rule)

New migration `0029_document_storage.sql` — additive, does not touch frozen migrations:

```sql
-- 0029_document_storage.sql — object-storage reference for the original file.
ALTER TABLE repository.documents
  ADD COLUMN IF NOT EXISTS storage_key   TEXT,            -- full object path within the bucket
  ADD COLUMN IF NOT EXISTS storage_bucket TEXT,           -- e.g. crie-documents-prod (env-resolved)
  ADD COLUMN IF NOT EXISTS byte_size      BIGINT,         -- original file size in bytes
  ADD COLUMN IF NOT EXISTS content_type   TEXT,           -- validated MIME type
  ADD COLUMN IF NOT EXISTS stored_at      TIMESTAMPTZ;    -- when the original was persisted

CREATE INDEX IF NOT EXISTS idx_documents_storage_key ON repository.documents (storage_key);
```

Notes:
- All columns nullable so the migration is safe on existing rows; `storage_key` is populated at ingestion going forward.
- `sha256` already exists and remains the content fingerprint; `storage_key` is the location. Both are carried in the reference tuple.
- No change to `monitoring.processing_history` (still append-only, INSERT-only from workflows).

Optional integrity table (recommended, additive):

```sql
CREATE TABLE IF NOT EXISTS repository.document_blobs (
  document_id  UUID PRIMARY KEY REFERENCES repository.documents(id) ON DELETE CASCADE,
  storage_key  TEXT NOT NULL,
  sha256       TEXT NOT NULL,
  byte_size    BIGINT,
  verified_at  TIMESTAMPTZ           -- last time stored bytes were re-hashed and matched sha256
);
```

---

## 5. Ingestion — store exactly once (WF-001 head)

New stage order at the front of WF-001, replacing "carry binary through the pipeline":

1. **Trigger + Download File** — obtain the binary once (Google Drive download), as today.
2. **Compute sha256** (SW-001/002, existing Init logic; reads binary once here).
3. **Duplicate check (SW-003)** — by `sha256`, unchanged (dev-bypass preserved).
4. **Store original (new node "Persist Original to Storage")** — upload the binary to
   `crie-documents-{env}/originals/{date}/{documentId}/{sha256}.{ext}` **exactly once**.
   - If SW-003 found a duplicate (production), skip upload and reuse the existing `storage_key`.
   - Idempotent: uploading the same key twice is a no-op / overwrite of identical bytes.
5. **Register (SW-004)** — INSERT `repository.documents` now also sets `storage_key`, `storage_bucket`, `byte_size`, `content_type`, `stored_at` (via the idempotent register already built).
6. **From here on, the item carries only `{ documentId, sha256, storageKey, correlationId }`.** Binary is dropped intentionally and never re-attached.

The existing "Re-attach File Binary" node is **removed** — it is obsolete under this design.

Upload mechanism options (pick per network policy):
- **n8n Supabase/HTTP node** uploads the buffer to Storage using the service-role key. Binary lives in memory only for this one node.
- If the file is already in a location Azure/Supabase can pull from, upload can be a server-side copy.

---

## 6. SW-005 under object storage (no binary in n8n)

New SW-005 flow:

1. **Trigger** receives `{ documentId, sha256, storageKey, correlationId }` (JSON only — crosses the boundary trivially, no binary marshalling concern).
2. **Load OCR settings** (Postgres) — unchanged.
3. **Mint signed URL** (Supabase `createSignedUrl(storageKey, ttl)`, short TTL e.g. 300s) via HTTP/Supabase node.
4. **Azure analyze** — POST `{ "urlSource": "<signed-url>" }` to the v4.0 analyze endpoint (`_overload=analyzeDocument&api-version=2024-11-30`). Azure fetches the file directly from storage. **The file never enters n8n memory.**
5. **Poll + shape** — unchanged (async poll loop for the analyze result, then enrich `{...incoming, ocr}`).

Fallback if signed-URL egress to Azure is not permitted:
- SW-005 downloads the object into a buffer and sends `base64Source` instead. Binary is then transient inside SW-005 only, never crosses back, and never touches WF-001. This is strictly better than Design B (no boundary crossing of bytes).

---

## 7. Retry behavior & resumability

Object storage makes both first-class:

- **Every stage can re-derive the file from `storageKey`.** A retried SW-005 (Azure timeout, throttle, worker crash) simply mints a fresh signed URL and re-calls — no dependence on in-flight binary.
- **Checkpoints already record stage/status** in `monitoring.processing_history`. Combined with a durable `storage_key`, a resumed run reads the document row, gets `storageKey`, and continues from the last completed stage. Resumability no longer requires replaying the upload.
- **Idempotent upload** (§5.4): re-running ingestion for the same `sha256` does not create duplicate objects; the key is content-addressed within the document folder.
- **§154 failure policy** is unchanged in shape but more robust: HUMAN_REVIEW / FAILED branches carry the same reference tuple, so an operator or re-run can fetch the exact original by `storageKey`.
- **Poison-message safety:** because the item is tiny, Queue Mode retries and DLQ handling are cheap; no large payloads clog the queue.

---

## 8. Lifecycle management

- **Retention:** storage lifecycle rules on `originals/{yyyy}/{mm}/{dd}/` (e.g. transition to cold tier after N days, delete after the compliance retention window). Because objects are date-partitioned, age-based rules are direct.
- **Erasure (GDPR / §-retention):** delete the `originals/.../{documentId}/` prefix + cascade the DB row; one prefix delete removes all artifacts for a document.
- **Integrity:** periodic job re-hashes stored objects and compares to `sha256` (writes `document_blobs.verified_at`). Detects silent storage corruption.
- **Orphan reconciliation:** scheduled check (fits WF-005 Administration) for storage objects with no DB row and DB rows with missing objects.
- **Access control:** private bucket; signed URLs with short TTL; service-role key held only where uploads/URL-minting happen. No credential in `storageKey`.

---

## 9. Impact on WF-001 through WF-005

| Workflow | Impact |
|---|---|
| **WF-001 Ingestion** | Add "Persist Original to Storage" node after dup-check; SW-004 register writes `storage_key` etc.; **remove the re-attach-binary node**; main item becomes the 4-field tuple; SW-005 rewired to signed-URL/urlSource. Biggest change, but removes all binary-propagation fragility. |
| **WF-002 Retrieval** | No document binary involved (works on embeddings/text). **No change** from this design. Still benefits from the tuple convention if it ever needs the original. |
| **WF-003 Reasoning** | Text/knowledge only. **No change.** |
| **WF-004 Output** | If it emits the original or a rendered artifact, it fetches by `storageKey` and writes derived outputs under `derived/{documentId}/`. Otherwise no change. |
| **WF-005 Administration** | Gains the storage integrity/orphan reconciliation job (§8). Fits its existing health/analytics fan-out. |

---

## 10. Impact on future modules

- **New workflows inherit the tuple convention:** any module needing the original fetches by `storageKey`; none carry binary. This is added to the Workflow Engineering Guidelines as mandatory.
- **Derived artifacts** (thumbnails, redacted copies, searchable PDFs from Azure) get sibling prefixes under the same `{documentId}/` folder — consistent, discoverable, deletable as a unit.
- **Multi-file / batch ingestion** scales naturally: each file is one small tuple; no memory blowup regardless of file size or batch count.
- **Provider portability:** `storageKey` + `storage_bucket` abstract the backend. Moving from Supabase Storage to Azure Blob/S3 changes the URL-minting node and bucket config, not the workflows.

---

## 11. Migration from the current architecture

Phased, additive, reversible:

1. **Schema:** apply `0029_document_storage.sql` (additive; safe on live DB).
2. **Provision bucket:** create `crie-documents-{env}`, private, with lifecycle rules.
3. **Ingestion cutover:** deploy WF-001 with the Persist-Original node + SW-004 storage columns + SW-005 signed-URL path. New documents get `storage_key` from now on.
4. **Backfill (optional):** for existing documents that still have their source available, a one-off job uploads originals and populates `storage_key`. Documents without a recoverable original keep `storage_key = NULL` and are flagged.
5. **Retire binary path:** once SW-005 signed-URL OCR is verified in staging, remove the re-attach-binary node and the base64/binary handling. The probe (Appendix A of the Engineering Guidelines) becomes moot for the main path.
6. **Rollback:** because changes are additive, reverting to the prior WF-001 version restores binary handling; storage rows are harmless if unused.

---

## 12. Why this is the standard, not a workaround

- Binary is stored **once**, in a system built for durable large-object storage, not shuttled through a workflow engine that copies and persists items.
- The workflow item is **tiny and uniform** everywhere, so the item-replacement behavior of Postgres/HTTP/sub-workflow nodes is irrelevant — there is nothing large to lose.
- **Memory, execution-log size, queue payloads** all become independent of document size.
- **Retry, resume, and fault tolerance** are inherent because the file is durable and re-derivable from a reference.
- It matches **enterprise norms** (content-addressed object storage + reference passing) and **fits CRIE's existing Supabase footprint**.

---

## Appendix — open decisions for Architecture Owner

1. Signed-URL-to-Azure (`urlSource`) vs download-then-`base64Source` inside SW-005 — depends on whether outbound egress from Azure to Supabase Storage is permitted by your network/security policy.
2. Signed-URL TTL (proposed 300s) and whether Azure's fetch latency for large files needs a longer window.
3. Whether to add the `repository.document_blobs` integrity table now or defer.
4. Backfill scope for pre-existing documents.
5. Bucket region/co-location with the Azure DI region to minimize cross-region egress cost and latency.
