# PR-006 — Proposal Writing

Canonical prompt ID per §173 catalog (R-04). Produces the proposal Response text,
plus the per-requirement Gap Analysis (§549) and Risk Register (§550) entries.
**No new prompt ID** is introduced for Gap/Risk — they are outputs of PR-006 (R-04).

Files (§626): `system.md`, `user.md`, `schema.json`, `examples/`, `README.md`.

- Does not compute `complianceLevel` (R-11) or `confidence` (R-10).
- Loaded via SW-022 Prompt Loader (§175); never hardcoded.
- Consumes the canonical Compliance Result (§295) fields for one requirement.
