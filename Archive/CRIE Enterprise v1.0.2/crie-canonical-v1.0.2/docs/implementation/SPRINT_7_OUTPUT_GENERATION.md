# Sprint 7 — Proposal Engine (WF-004 Output Generation)

_All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
modification, distribution, or commercial use is prohibited without written
permission._

**Version:** `v0.8.0` · **Depends on:** Sprint 6 (`v0.7.0`) · **Spec:**
CRIE Enterprise Specification v1.1.1

## Scope

Sprint 7 implements **WF-004 Output Generation** (R-02): the terminus of the
Proposal pipeline `WF-002 → WF-003 → WF-004`. It transforms the canonical
Compliance Results (§295) produced by WF-003 into the **Proposal Package** (§552).
This module contains **no business reasoning** (§98); it formats, aggregates,
validates, and exports, and never modifies the reasoning result (§99).

## Deliverables (backlog mapping)

| Task | Deliverable | Spec |
|---|---|---|
| S7-1 | Compliance Matrix, one row per requirement, required columns | §102, §547 |
| S7-2 | Executive Summary (PR-007) — deterministic counts + narrative | §109, §548, R-04 |
| S7-3 | Evidence Report — every evidence item used | §110 |
| S7-4 | Gap Analysis via PR-006/PR-007 (no new prompt ID) | §549, R-04 |
| S7-5 | Risk Register via PR-006/PR-007 (no new prompt ID) | §550, R-04 |
| S7-6 | PR-006 Proposal Writing prompt | §173 |
| S7-7 | SW-025 Google Sheets Writer + configurable column mapping | §265, §363–364 |
| S7-8 | Review states + reviewer workflow | §106–107, §551 |
| S7-9 | Export rules (deterministic) + audit trail | §112–113 |

## Artifacts

- `config/output.config.yaml` — column mapping (§364, no hardcoded columns),
  review states (§107/§551), export rules (§113), gap/risk vocabularies. Source
  of truth per R-08.
- `contracts/proposal_package.contract.json` — Proposal Package shape; a
  container over §295, no invented reasoning fields.
- `prompts/PR-006/`, `prompts/PR-007/` — canonical §173 prompts (system, user,
  schema, examples, README per §626). Gap Analysis (§549) and Risk Register
  (§550) are outputs of PR-006/PR-007 — **no PR-009+ introduced** (R-04).
- `workflows/master/WF-004_Output_Generation.json` — importable n8n master
  workflow.
- `workflows/workflow_registry.sprint7.json` — activation fragment for WF-004 and
  SW-025 (introduces no new IDs; §634 immutability respected).
- `src/output_generation/` — runnable engine:
  - `wf004_output_generation.py` — deterministic package assembly, matrix,
    executive summary, evidence report, gap/risk collection, statistics, audit.
  - `sw025_sheets_writer.py` — configuration-driven Google Sheets mapping.
  - `review_workflow.py` — review state machine; rejected → WF-003 (§106/§551).
- `tests/test_sprint7.py` — 30 acceptance tests (all passing).
- `tests/sample_requirements.json`, `tests/sample_proposal_package.json` — the
  exit-gate sample requirement set and the generated package.

## Key decisions honored

- **R-02** — WF-004 is Output Generation; pipeline WF-002 → WF-003 → WF-004; no
  WF-006. Administration (WF-005) is **out of scope** (Sprint 8).
- **R-03** — single canonical Compliance Result contract (§295) is the sole input.
- **R-04** — Gap Analysis and Risk Register produced by PR-006/PR-007; no new
  prompt IDs.
- **R-08** — output formatting authored in YAML.
- **R-10 / R-11** — confidence and complianceLevel are treated as fixed
  platform-computed inputs; WF-004 never recomputes reasoning.

## Export determinism (§113)

`generate_proposal_package` is pure and order-preserving; identical inputs yield
byte-identical JSON. Verified by `TestExportDeterminism`.

## Deferred (accepted)

Live Google Sheets I/O runs through the Provider Adapter layer in the target
deployment (scaffold-then-provision). SW-025 produces the deterministic row
payload the adapter consumes; no live spreadsheet is written in the build
environment.

## Exit gate

Complete Proposal Package generated from the sample requirement set (5
requirements → matrix + summary + evidence + 3 gaps + 2 risks + statistics +
audit). Confirmed by `TestExitGate`. **Tag `v0.8.0`.**
