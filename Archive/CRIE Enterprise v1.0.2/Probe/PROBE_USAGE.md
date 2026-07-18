# Binary-Boundary Probe — Usage (one-shot, removable)

## What this is
A standalone 2-node sub-workflow that reports whether binary crosses the Execute Workflow
boundary on THIS n8n instance. It has NO database writes, NO external calls, NO state changes.
It is not part of CRIE runtime. Delete it after you capture the result.

## How to run it (choose one)

### Option 1 — call it from WF-001 temporarily (most representative)
This reproduces the exact path SW-005 sees (Download File -> ... -> Execute Workflow -> sub-trigger).
1. Import `PROBE_Binary_Boundary.json`.
2. In WF-001, TEMPORARILY point the existing `SW-005 Azure OCR` Execute Workflow node at
   this probe instead of SW-005 (pick it from the dropdown). Change nothing else.
3. Run WF-001 with a real file (dev bypass on is fine).
4. Open the probe's sub-execution -> read the `Report Binary Availability` output JSON.
5. Revert the Execute Workflow node back to SW-005. Delete the probe workflow.

### Option 2 — minimal throwaway caller (fully isolated from CRIE)
If you do not want to touch WF-001 at all:
1. Import `PROBE_Binary_Boundary.json`.
2. Create a scratch workflow: Manual Trigger -> HTTP Request (or Read/Download a small file to
   get an `item.binary.data`) -> Execute Workflow (target = this probe).
3. Run it once, read the probe output, delete both scratch and probe.

Option 1 is preferred because it measures the real WF-001 boundary + your filesystem binary mode.

## Reading the result

| Output | Meaning | Decision |
|---|---|---|
| `getBinaryDataBuffer_ok: true` (bytes > 0) | Binary crosses AND is readable in the child | **Design A viable** |
| `input_has_binary: true` but `getBinaryDataBuffer_ok: false` | Pointer arrives but child cannot resolve it (filesystem cross-execution failure) | **Design A rejected** — use B or object storage |
| `input_has_binary: false` | Binary does not cross the boundary at all | **Design A rejected** |
| `n8n_binary_mode_hint` | Confirms filesystem/pointer vs inline | context |
| `trigger_has_binary` vs `input_has_binary` | Whether node-reference specifically works vs the item chain | refines A design |

Paste the full JSON back and the platform-wide architecture decision can be finalized.
