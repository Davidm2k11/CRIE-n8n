# PR-007 — Executive Summary

Canonical prompt ID per §173 catalog (R-04). Produces the Executive Summary
narrative (§109/§548): key risks and recommended next steps. Numeric aggregates
(counts, percentages) are computed deterministically by the platform and passed in
as fixed inputs — PR-007 never recomputes them (R-10/R-11, §548 "validated results
only").

Per R-04, PR-007 (with PR-006) also backs the Gap Analysis and Risk Register
narrative rollups. No new prompt ID is introduced.

Files (§626): `system.md`, `user.md`, `schema.json`, `examples/`, `README.md`.
