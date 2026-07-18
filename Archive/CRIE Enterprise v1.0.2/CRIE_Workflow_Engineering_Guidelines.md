# CRIE Workflow Engineering Guidelines

**Scope:** All n8n workflows in the CRIE project (WF-001…WF-005, all SW-* sub-workflows, all UT-* utilities).
**Platform of record:** n8n 2.29.9 (Queue Mode), Supabase/PostgreSQL, filesystem binary storage mode.
**Purpose:** Prevent the recurring class of state-loss and binary-loss defects discovered during WF-001 deployment. These rules are mandatory for future workflows so the same bugs cannot be reintroduced.

> Status note on binary across the Execute Workflow boundary: one rule in §3/§7 is marked **UNVERIFIED** and gated on a runtime probe (Appendix A). Do not treat the node-reference-across-boundary approach as approved until the probe passes on the target instance.

---

## 0. The core model

Every item flowing between n8n nodes has two independent parts:

- `item.json` — structured workflow state (documentId, correlationId, sha256, ocr, metadata, knowledge, chunks, embeddings, …).
- `item.binary` — binary attachments (the document file), stored by reference in filesystem mode (the `.data` field is a storage pointer, **not** the bytes).

The root cause of the WF-001 defects was carrying **both** concerns on the same item through nodes that **replace** the item. State and binary have different lifecycles and must be handled by different mechanisms. The guidelines below codify that separation.

---

## 1. When to propagate workflow state via items

Use item propagation (`item.json` flowing node-to-node) as the **default** for state that:

- is produced by a node and consumed by the **immediately following** node(s), and
- flows along a path with **no item-replacing node** in between (see §4).

Rules:

- **Code nodes must spread prior state:** `return [{ json: { ...$json, newField } }]`. Never return a fresh object that silently drops accumulated fields.
- **Enrichment, not replacement:** a processing node's contract is `output = { ...input, itsResult }`. This applies to every SW sub-workflow (`output = { ...incoming, <result> }`).
- Item propagation is appropriate and sufficient across `IF`, `Code` (spreading), and `NoOp` nodes.

Do **not** rely on item propagation across an item-replacing node (§4). State needed on the far side of such a node must use node references (§2) or explicit passthrough (§5).

---

## 2. When to use node references (`$('NodeName')`)

Use a node reference when a consumer needs data that was produced **upstream of one or more item-replacing nodes**, i.e. the item chain cannot carry it intact.

- **Canonical use:** every SW `shape` node reconstructs output via `$('When Executed by WF-001').first().json` rather than trusting the item to survive the intervening Postgres/HTTP nodes. This is robust and is the required pattern.
- `$('X').item` respects paired-item lineage; `$('X').first()` takes the first item. Use `.item` inside per-item Code; `.first()` in run-once-for-all-items Code.

**Hard constraint on scope:** `$('X')` resolves against the **current workflow execution only**. Inside a sub-workflow, `$('When Executed by WF-001')` refers to that sub-workflow's **own trigger**, not to any node in the parent (WF-001) execution. A sub-workflow **cannot** reach into the parent execution's node outputs by reference. Any design that assumes cross-execution node reference is invalid.

---

## 3. When binary must NOT be propagated (and how to handle it instead)

**Never assume binary survives an item-replacing node, and never try to carry binary further than the single point where it is consumed.**

Concrete rules:

1. **Identify the one consumer.** In CRIE the only binary consumer is SW-005's Azure OCR HTTP node (`contentType: binaryData`, field `data`) and WF-001's Init node (SHA-256 hashing). No other workflow node reads the file. Do not thread binary anywhere it is not consumed.
2. **Read bytes via the official API only:** `await this.helpers.getBinaryDataBuffer(itemIndex, 'data')`. Never read `item.binary.data.data` directly — in filesystem/S3 mode that is a pointer, not the payload. (n8n docs explicitly warn against `items[0].binary.data.data`.)
3. **Binary across the Execute Workflow boundary — UNVERIFIED, gated:** Whether a sub-workflow can read the file the parent passed depends on runtime marshalling in this n8n build and on filesystem binary mode. Until the Appendix A probe passes, treat cross-boundary binary as **not reliably available by reference**. If the probe fails, do **not** pass the file as binary across the boundary at all — pass it as base64 in `json` and rebuild it in the sub-workflow (§7, Design B).
4. **Do not add a re-attach node after every replacer.** Iterative re-attachment is a symptom, not a fix. Binary is re-established once, at the boundary or at the point of use, per the approved design in §7.
5. **Postgres-before-binary-consumer pattern (mandatory):** if a Postgres node sits immediately before a binary consumer (as in SW-005: Load OCR Provider Settings → Azure), the Postgres node drops `item.binary`. Restore it from the sub-workflow trigger by node reference in a Code node placed directly before the consumer: `return [{ json: $json, binary: $('<trigger name>').first().binary }];`. This is verified working across the Execute Workflow boundary (binary-boundary probe: `getBinaryDataBuffer` returned the full file; `$('trigger').first().binary` resolved). Any future SW workflow with this shape MUST apply the same step. Iterative re-attachment is a symptom, not a fix. Binary is re-established once, at the boundary or at the point of use, per the approved design in §7.

---

## 3.5.1 Worked example — state across an HTTP node INSIDE a loop

§3.5 says HTTP Request nodes replace the item. This is the case that bites hardest, because the
state is not merely dropped once — it is dropped on **every loop iteration**.

```
build-request()  ->  { ...item, _bx, messages }     state present
        |
        v
OpenAI (httpRequest)  ->  { id, choices, usage }    *** ITEM REPLACED — _bx GONE ***
        |
        v
collect()        ->  $json._bx === undefined        *** THROWS ***
```

**Wrong:** `const st = { ...$json._bx };`  — the item no longer has it.

**Right:** restore from the last node before the HTTP call that carried the state:

```javascript
const req = $('build-request() — Render Batch').first().json;
if (!req || !req._bx) throw new Error('could not restore loop state (§3.5)');
const st = { ...req._bx };
```

**Why this is allowed when §3.6 forbids node references in loops.** The two are different reads:

| Read | Reliable? |
|---|---|
| **Current run** of an upstream node (`$('X').first()`) | **Yes.** Resolves within the current iteration. |
| **Earlier runs** of a loop node (`$('X').all(0, r)` over run history) | **No.** §3.6 — returns only the first run. |

`collect()` needs the *current* iteration's state, not history. That read is sound, and SW-005's
`poll-eval` relies on the same mechanism across its own HTTP node.

**Guard it.** Stamp a marker on the request and verify it after restoring, so a mis-resolved
reference fails loudly instead of attributing a response to the wrong iteration:

```javascript
if (req._batchMarker != null && Number(req._batchMarker) !== Number(batch.index)) {
  throw new Error('state/response mismatch — restored batch ' + batch.index +
                  ' but the request was for batch ' + req._batchMarker);
}
```

Also rebuild the outgoing item from the trigger (`$('When Executed by WF-001').first().json`), not
from `$json` — `$json` is the API response, and spreading it would leak `choices`/`usage` into the loop.

## 3.6 Loop history is NOT reconstructible downstream (n8n 2.29.9)

**Rule: a Code node downstream of a Wait-loop MUST consume the item on the wire. It MUST NOT
attempt to enumerate the loop's earlier runs via `$('<loop node>').all(0, runIndex)`.**

Measured on n8n 2.29.9: in a Wait-node polling loop, `$('poll node').all(0, r)` returned only the
**first** run to a downstream Code node — a stale, non-terminal iteration — even when the execution
viewer plainly showed a later, terminal run. `.runIndex`, `.first()`, `.last()` and `.item` all
resolved to the same first run. The loop history visible in the UI is **not** available to the
expression layer.

**The correct pattern:** let the IF node that exits the loop do the selection, and have the
downstream node read `$json`.

```
poll -> evaluate -> terminal? --[false]--> wait (loop)
                        |
                     [true]
                        v
                   succeeded? --[false]--> fail path
                        |
                     [true]
                        v
                   consumer   <-- reads $json. The gates already PROVED this item is
                                   the terminal, successful one. No history lookup.
```

The consumer should assert the invariant and throw if violated (`_poll.terminal !== true`), rather
than silently emitting an empty result. An empty-but-structurally-valid object propagating
downstream is far harder to debug than an immediate failure.

**Cost of ignoring this:** a normalizer that read loop history produced `ocr.pages = []` /
`ocr.raw = {}` — structurally valid, completely empty — and the failure only surfaced four nodes
later. It cost several full debugging cycles.

## 4. Node types that REPLACE the item

These emit a **new** item built from their own result. `item.binary` is dropped and `item.json` is overwritten. Treat everything downstream as starting from scratch unless you take explicit action.

| Node type | Why it replaces | Notes |
|---|---|---|
| `postgres` (Execute Query) | Output = query rows | Drops binary; json becomes the row set. **No "include binary" option exists.** |
| `httpRequest` | Output = HTTP response | Drops binary unless response is explicitly mapped; response body becomes json. |
| `set` / `editFields` | Rebuilds the item | Drops binary unless **Include Binary** enabled; drops other json unless **Include Other Input Fields** enabled. |
| `executeWorkflow` (Execute Sub-workflow) | Output = sub-workflow return | The returned item replaces the caller's item. Binary crossing is version/mode dependent (§3.3). |
| `code` returning a fresh object | Whatever you return | Replaces unless you spread `...$json` and carry `binary`. |
| `merge` (most modes) | Combines inputs | Resulting shape depends on mode; do not assume binary or full json survives. |
| `splitOut`, `itemLists`, aggregate nodes | Restructure items | Drop binary unless **Include Binary** enabled. |

---

## 5. Node types that PRESERVE the item

| Node type | Behavior |
|---|---|
| `if` / `switch` | Route the item unchanged (json + binary both pass). |
| `noOp` | Pass-through. |
| `code` that spreads state | `return [{ json: { ...$json, x }, binary: $input.item.binary }]` preserves both. Only preserves what you explicitly carry. |
| `filter` | Passes matching items unchanged. |
| Trigger nodes (producers) | `googleDrive`/Download produces binary; `executeWorkflowTrigger` (v1.1, passThrough) forwards json (+binary subject to §3.3). |

Note: "preserve" for Code nodes is **conditional** — a Code node preserves only the fields you spread and the binary you explicitly re-attach. There is no implicit carry.

---

## 6. Passthrough techniques for item-replacing nodes (when the node must stay inline)

When an item-replacing node sits on the main path and cannot be moved off-stream, and downstream needs its prior state:

- **Postgres — carry scalar state as columns:** append a trailing `SELECT '{{$json.field}}' AS "field", …` (or a CTE) so the emitted row re-introduces needed scalar fields plus any produced value (documentId, certified). Works only for scalar/string state — **cannot** carry arrays/objects like `chunks[]` or `ocr` (use §2 node reference or §6 off-stream instead).
- **Move pure side-effects off the main stream:** logging/checkpoint writes that produce nothing the main path consumes must be **side branches** — predecessor points to both the successor (main wire) and the checkpoint (terminating branch). The checkpoint's item replacement then never touches the main item. This is mandatory for all monitoring/telemetry/checkpoint writes.
- **Set/Edit Fields:** always enable **Include Other Input Fields**; enable **Include Binary** only if binary is genuinely needed downstream (usually it is not — see §3).

---

## 7. The approved binary architecture (single coherent design)

Binary is decoupled from the item chain and established exactly once, at the boundary of the workflow that consumes it. Two designs; which one is approved depends on the Appendix A probe.

**Design A — node-reference at point of use (only if probe passes):**
- Parent passes the item across the Execute Workflow boundary with the trigger in v1.1 `passThrough`.
- Inside the consuming sub-workflow, the binary consumer reads bytes via `getBinaryDataBuffer(0,'data')` immediately after the trigger, **before** any Postgres/HTTP node. If a settings-load Postgres node is needed first, the consumer reads binary by reference from the trigger (`$('When Executed by WF-001')`) — valid because it is the sub-workflow's own trigger (§2).
- No re-attach node in the parent; no threading binary through Postgres nodes.

**Design B — base64 in json (mandatory fallback if probe fails):**
- In the parent, at the point binary is available, read it to a Buffer and attach base64 to `json` (e.g. `json.fileB64`, plus `json.mimeType`, `json.filename`). `json` crosses the boundary intact regardless of binary marshalling.
- Inside the sub-workflow, rebuild binary with `this.helpers.prepareBinaryData(Buffer.from(json.fileB64,'base64'), json.filename, json.mimeType)` immediately before the consumer.
- This moves the **bytes**, not a pointer, so it is immune to filesystem-mode cross-execution pointer resolution failures. Cost: base64 inflates payload ~33%; acceptable for single-document ingestion, reconsider for very large files.

Until the probe result is known, **Design B is the safe default** for any new workflow that must hand a file to a sub-workflow.

---

## 8. Mandatory patterns for all future workflows (WF-002+, new SW/UT)

1. **Separate concerns:** never rely on one item to carry both binary and evolving state across item-replacing nodes. State via §1/§2; binary via §7.
2. **Enrichment contract:** every processing node and every sub-workflow returns `{ ...input, result }`. No silent drops.
3. **Sub-workflow output reconstruction:** `shape`/output nodes read incoming state via `$('<trigger name>')`, never by trusting the item to survive internal Postgres/HTTP nodes.
4. **Checkpoints/telemetry off-stream:** all monitoring writes are terminating side branches; they must never be on the main item path.
5. **Binary read only via `getBinaryDataBuffer`;** never `binary.data.data`.
6. **No cross-execution node references:** `$()` is current-execution only. Design sub-workflow inputs explicitly (fields/JSON example or documented passThrough contract).
7. **Every item-replacing node on a main path gets a written justification** in the workflow's notes: what state must survive it, and how (columns, node-ref, or off-stream).
8. **Pre-merge audit for new workflows:** before adding a workflow to the project, run the item-behavior audit (classify every node REPLACE/PRESERVE/PASS; for each REPLACE, confirm downstream json/binary needs are met). No workflow ships without this audit.
9. **Verify runtime-dependent behavior by probe, not by documentation.** Binary marshalling, `this.helpers` availability, and Code-node runtime constraints must be confirmed on the target instance before being relied upon.

---

## 9. Fan-out/fan-in workflows (e.g. WF-005)

Aggregation workflows that fan out to parallel branches and converge (WF-005) do **not** have the linear-accumulation problem: the convergence node uses `$input.all()` to collect branch results and `$('Initialize')` for shared state. This is correct and preferred for parallel work. The item-replacement rules (§4) still apply per branch, but state is reassembled at the convergence node by reference, not by threading one item through all branches.

---

## Appendix A — Binary-across-boundary probe (run before approving Design A)

Add this Code node in the consuming sub-workflow immediately after its trigger, run the parent once with a real file, and record the output:

```javascript
// PROBE — remove after testing.
const viaInput   = $input.first().binary;
const viaTrigger = $('When Executed by WF-001').first().binary;
let bufferOk = false, bufferErr = null;
try {
  const buf = await this.helpers.getBinaryDataBuffer(0, 'data');
  bufferOk = Buffer.isBuffer(buf) && buf.length > 0;
} catch (e) { bufferErr = String(e).slice(0, 200); }
return [{ json: {
  input_has_binary:   !!viaInput,
  input_binary_keys:  viaInput ? Object.keys(viaInput) : [],
  trigger_has_binary: !!viaTrigger,
  data_pointer:       viaInput?.data?.id || viaInput?.data?.data || null,
  getBinaryDataBuffer_ok: bufferOk,
  getBinaryDataBuffer_error: bufferErr,
}}];
```

Decision rule:
- `getBinaryDataBuffer_ok: true` → **Design A approved.** Binary crosses the boundary and is readable.
- `input_has_binary: true` but `getBinaryDataBuffer_ok: false` → **Design A rejected; use Design B.** Pointer arrives but is unresolvable in the child execution (filesystem-mode cross-execution failure).
- `trigger_has_binary` vs `input_has_binary` divergence → tells whether node-reference specifically works vs. the item chain.

**Current status: UNVERIFIED.** Probe not yet run on the target instance. Design B is the safe default until this is filled in.

---

## Appendix B — Status of WF-001 against these guidelines

| Concern | Status |
|---|---|
| JSON state propagation | Compliant — Code nodes spread `$json`; SW enrichment; Postgres passthrough columns; checkpoints off-stream. |
| Sub-workflow output reconstruction | Compliant — shape nodes read `$('When Executed by WF-001')`. |
| Checkpoints off-stream | Compliant — 4 checkpoints are terminating side branches. |
| Binary to Init (SHA-256) | Compliant — Init is immediately after Download; no replacer between. |
| Binary to SW-005 OCR | **Blocked on Appendix A probe.** The internal `Load OCR Provider Settings` Postgres node sits between trigger and Azure; whether binary is readable there depends on the probe. Do not consider WF-001 OCR path complete until resolved. |
