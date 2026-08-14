# PR-4 Acceptance Record — WF-001 ingestion cutover to storage-backed processing

Object Storage roadmap, PR-4. This is the acceptance record for the cutover: every
criterion, its outcome, and the evidence behind it. One criterion was amended by
Architecture Owner ruling; that amendment and the evidence that justified it are
recorded here in full rather than folded away.

Artifacts under test: `WF-001 Knowledge Ingestion (portable)`, `SW-005 Azure OCR`,
`SW-029 Persist Original`, `SW-030 Azure Analyze (URL isolation)`.
Instance: n8n 2.29.9, Supabase Postgres 17.6 + Storage, Azure Document Intelligence
`prebuilt-layout`, OpenAI `gpt-4o` / `text-embedding-3-small`.

---

## 1. Amended criterion — large-document memory

### 1.1 Status

**RESOLVED BY APPROVED ACCEPTANCE-CRITERION AMENDMENT.** Not a failed criterion.

The original criterion rested on a premise that is incompatible with this n8n
configuration. It was replaced, with approval, by a criterion that tests what the
architecture actually guarantees.

### 1.2 Superseded criterion

> Record pre-change worker RSS baseline, post-change peak RSS, whether the run
> completes and whether heap OOM occurs. Demonstrate that the storage-backed
> architecture materially avoids the previous binary-memory pressure.

### 1.3 Approved criterion (in force)

> **"Demonstrate a ~60-page document completes without OOM, and that no whole-file
> buffer is retained past the storage boundary."**

### 1.4 Evidence behind the amendment

1. **The first benchmark was invalid.** It sampled `docker stats` MemUsage — the
   cgroup's memory usage **including page cache** — not true RSS. n8n runs
   `binaryMode: "separate"` and writes the document to disk, so the two arms dirty
   different amounts of page cache. It also used one run per arm with no container
   restart between them, so the V8 high-water mark carried across. Its figures
   (1591 MiB vs 2192 MiB) are withdrawn and must not be reused.

2. **The corrected A/B** used anonymous RSS summed across every container PID (Code
   nodes run in the task runner, a separate process), page cache recorded separately,
   a fresh container per run, alternating arm order, byte-identical fixtures
   (12,676,837 bytes each), and three runs per arm.

3. **All six runs completed successfully with identical output** — PROCESSED, 96
   knowledge units, 96 chunks each. The comparison is like-for-like.

4. **The ranges overlap.**

   | arm | runs (MiB) | median | min | max | range |
   |---|---|---|---|---|---|
   | PR-4, storage-backed | 2263, 2296, 2305 | 2296 | 2263 | 2305 | 42 |
   | pre-PR-4, binary path | 2363, 1844, 1938 | 1938 | 1844 | 2363 | **519** |

   The binary path's highest run (2363) exceeds every storage-backed run, and its
   spread (519 MiB) is larger than the median gap (358 MiB).

5. **`binaryMode: "separate"` already streams the binary from disk.** `HttpRequestV3`
   calls `helpers.getBinaryStream(binaryData.id)` whenever the binary carries an id,
   which it does in filesystem mode — for the Supabase upload *and* for the legacy
   Azure submit. Neither arm buffers the file for transport.

6. **PR-4 introduces only ~24 MiB of measured whole-file materialisation** at the
   storage boundary: `getBinaryDataBuffer` (required for magic-byte detection and the
   digest) plus, before the optimisation below, the hash's padded copy. Measured at
   12.1 MiB each (arrayBuffers, external and rss all move together).

7. **The dominant consumption is downstream OCR/LLM processing common to both
   architectures** — OCR normalisation and SW-008's batch loop, identical either side
   of the cutover. ~24 MiB is about 1% of a 2.3 GiB peak.

8. **No meaningful PR-4 memory regression was established.** No mechanism exists for a
   difference of the observed magnitude, and the arms overlap.

### 1.5 Optimisations implemented during the investigation

Both are genuine reductions in avoidable duplication, kept on their own merit. Neither
was performed to manufacture an RSS reduction, and neither materially moves peak RSS.

- **Streaming SHA-256** (`SW-029 Prepare Object`) — compresses 64-byte blocks directly
  from the source buffer and allocates a fixed 64/128-byte tail, replacing a
  whole-file padded copy (12.1 MiB for a 12.7 MB document). Digests are bit-identical:
  260 assertions against Node's `crypto`, covering every length 0–200, both sides of
  each padding boundary, 40 random sizes and a 12.7 MB buffer. Cross-validated live —
  `repository.documents.sha256` is written by WF-001's `Init` using the *original*
  implementation, and SW-029's M2b guard compares the *new* digest against it; a real
  12.7 MB document reached PROCESSED without the guard firing.
- **Bounded OOXML probe** (`SW-029 Prepare Object`) — replaces `buf.toString('latin1')`
  over the whole file with two 256 KB windows (a ZIP names its parts in the local file
  headers at the start and the central directory at the end), falling back to the full
  scan *before* throwing, so the bounded path is a shortcut and never a correctness
  change. Regression-tested with the marker placed outside both windows.

### 1.6 Verification of the amended criterion

| Clause | Evidence | Result |
|---|---|---|
| ~60-page document completes without OOM | 60-page / 12.68 MB fixture, 480 paragraphs; PROCESSED with 96 KUs; reproduced across 7 runs (3 storage-arm benchmark runs, 3 binary-arm, 1 post-optimisation); no OOM in any | **PASS** |
| No whole-file buffer past the storage boundary | 26 nodes reachable after SW-029: none calls `getBinaryDataBuffer`/`prepareBinaryData` or carries a `binary:` property. Only three nodes touch the file, all pre-boundary: `Download File`, `Init (SW-001/002)` (dup-check hash), `Attach Binary → SW-029`. SW-029 returns JSON only. On the signed-URL path neither `Build Analyze Request` nor SW-030 materialises the file | **PASS** |

---

## 2. Full PR-4 acceptance set

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | English PDF → PROCESSED | **PASS** | `CRIE-EN-A.pdf`: 9 KUs, 9 evidence/citations/chunks/embeddings @ vector(1536), history to `Certification:COMPLETED` |
| 2 | Arabic PDF → PROCESSED, KUs stay Arabic | **PASS** | Real Drive-triggered run (exec 345, `mode: "trigger"`), 9.16 MB: 112 KUs, **112 match `[؀-ۿ]`, 0 pure-Latin** |
| 3 | ~60-page document completes | **PASS** | 12.68 MB / 60 pages / 480 paragraphs → 96 KUs, exactly the 96 planted normative statements |
| 4 | SW-014 commits without `invalid input syntax for type uuid: ""` | **PASS** | `Write ok?` true on every run; repository rows written |
| 5 | No false HUMAN_REVIEW | **PASS** | All acceptance runs reached `Emit CERTIFIED` directly |
| 6 | `Re-attach File Binary` removed from the main path | **PASS (with recorded deviation)** | Renamed `Attach Binary → SW-029 (storage boundary)`; it is the *only* binary attach and cannot be zero — SW-029 must receive the bytes to upload them |
| 7 | No main-path node carries `item.binary` | **PASS** | See §1.6 clause 2 |
| 8 | `documents.storage_key IS NOT NULL` and `sha256(stored) == documents.sha256` | **PASS** | Objects downloaded and re-hashed: 9.16 MB Arabic and 12.68 MB recovered document both match; 0 duplicate keys, 0 orphaned objects, 0 size mismatches |
| 9 | Resumability from `storage_key` | **PASS** | SIGKILL 32 s after persist, mid-extraction → `REGISTERED`, 0 KUs. Recovery workflow with **zero Drive nodes and zero binary access** → PROCESSED, 96 KUs. `stored_at` unchanged, object `updated_at == created_at`, re-hash matches |
| 10 | Signed-URL OCR primary path live | **PASS** | `ocrInputMode = signedUrl`; every PR-4 run resolved `SIGNED-URL(primary)` (`Build Analyze Request` + SW-030, `Fetch Object from Storage` false) |
| 11 | Fallback preserved and selectable | **PASS** | Pre-PR-4 baseline arm resolved `legacy-binary` under the same config, confirming selection works in both directions |
| 12 | Execution-data security (probe G) | **PASS** | Real production execution 345, 30.7 MB persisted payload: 0 occurrences of `token=`, `object/sign`, `supabase.co`, `urlSource`, `signedURL`, `service_role`, `Bearer ey` |
| 13 | `python ci/validate_workflows.py` exit 0 | **PASS** | Green on the final tree |
| 14 | Large-document memory | **AMENDED — PASS** | See §1 |

---

## 3. Notes carried forward (not PR-4 blockers)

- **SW-008 batch planner** is calibrated to 0.30 KU/paragraph and fails *loudly* on
  documents far denser than that. A fixture measuring ≥2.22 KU/paragraph (three
  normative statements per OCR paragraph) exceeded the completion budget. No production
  configuration change was justified: the density was an artifact of that fixture, and
  the real corpus processes correctly at 0.30.
- Test documents (`CRIE-*`, `_probe-sw029`) remain as `repository.documents` rows.
  Decision D5: a documents row cannot currently be deleted — the `ON DELETE CASCADE`
  from `monitoring.processing_history` fires that table's append-only trigger.
- Backfill of pre-storage documents is **PR-5** and out of scope here.
