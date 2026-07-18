# Sprint 6 — Enterprise Reasoning (WF-003)

_All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
modification, distribution, or commercial use is prohibited without written
permission._

**Version:** `v0.7.0` · **Spec:** CRIE Enterprise Specification v1.1.1
**Depends on:** Sprint 5 (Context Package, §294) · **Blocks:** Sprint 7 (WF-004)

## 1. Objective
Implement the Enterprise Reasoning Engine WF-003 (§156): transform a single
Context Package into a valid, single-contract Compliance Result (§295), with the
compliance decision derived deterministically and confidence computed by the
platform.

## 2. Backlog coverage

| Item | Deliverable | Spec / decision |
|---|---|---|
| S6-1 | SW-022 Prompt Loader — loads PR-004, injects variables | §262, §173, §175, §176 |
| S6-2 | SW-023 Enterprise LLM — explanation + evidence mapping only | §263, R-11 |
| S6-3 | Deterministic `complianceLevel` (sufficiency §481 + matrix §480) | R-11, §478–481 |
| S6-4 | Platform-computed `confidence`; `modelSelfConfidence` input only | R-10, §89, §483 |
| S6-5 | SW-024 Output Validator (PR-005) + JSON validation | §264, §90, §298 |
| S6-6 | Citation re-linking via `evidenceId` | R-06, §88, §291 |
| S6-7 | Hallucination detection + self-validation | §493–494 |
| S6-8 | Human-review triggers/decision | §91, §491 |
| S6-9 | Emit single Compliance Result contract | R-03, §295 |

## 3. Execution flow (§156 / §85)
```
Receive Context → Validate Context → SW-022 Load Prompt (PR-004)
  → SW-023 Enterprise LLM → Derive complianceLevel + confidence
  → Attach citations (R-06) → SW-024 Output Validator + self-validation
  → [invalid → regenerate, up to maxRetries] → Return Compliance Result (§295)
```
The full sequence executes with no shortcuts (non-bypass, §599/§608).

## 4. Key design decisions (traced to reconciliations)

**R-11 — deterministic decision.** The LLM never assigns the compliance level.
It emits an `evidenceSignal` (one of six §480 keys) plus an evidence-to-conclusion
mapping and free-text explanation. The platform applies the §481 sufficiency gate
first (≥1 Knowledge Unit **and** ≥1 Evidence **and** ≥1 Citation, else
*Insufficient Evidence*), then the §480 matrix. Unknown signals fail safe to
*Insufficient Evidence*. A model-suggested level is advisory only.

**R-10 — platform confidence.** `confidence` is computed from the §483 factors
(retrieval confidence, evidence quality, mean authority normalized from §439,
citation coverage, consistency). Weights live in `reasoning.config.yaml` and are
configurable (§484). The model's self-reported value is stored as
`modelSelfConfidence` and never enters the computation.

**R-06 — citation re-linking.** Citations are projected onto the §291 canonical
contract (with `evidenceId`) and re-linked to their owning Evidence Objects.
Citations that cannot round-trip to a known `evidenceId` are dropped (§88) and
flagged by hallucination detection (§493).

**R-03 — one contract.** WF-003 emits exactly the §295 superset. The end-to-end
test asserts the produced keys equal the shipped contract file's keys.

## 5. Guardrails & safety
- §178 guardrails and §177 model settings are owned by the prompt (PR-004/PR-005),
  not the workflow.
- §493 hallucination detection removes unsupported statements before publish.
- §494 self-validation runs an ordered gate; invalid output is regenerated (§264).
- §491 human review is explicit and triggered by any single condition.

## 6. Environment notes (accepted risks, unchanged)
- No live datastore/provider in the build environment. WF-003 is verified against
  in-memory adapter doubles that drive the real deterministic logic; live
  application against Supabase/pgvector and live LLM/embedding providers occurs at
  the infrastructure integration stage (accepted scaffold-then-provision model).
- The LLM call is delegated to the Sprint-1 Provider Adapter layer; no provider
  SDK is embedded.

## 7. Verification
- `python -m unittest discover -s tests` → **32 tests, all passing**.
- Config, prompt manifest, workflow JSON, and contracts parse cleanly.
- End-to-end demo produces a valid §295 Compliance Result (Fully Compliant path)
  and correctly forces review on the Insufficient Evidence and conflict paths.

## 8. Sprint isolation
No WF-004 / Output Generation logic (Compliance Matrix, reports, Google Sheets)
is present — that is Sprint 7. No placeholders for future sprints were created.

## 9. Files
```
config/reasoning.config.yaml
contracts/compliance_result.contract.json
contracts/citation.contract.json
prompts/prompt_registry.sprint6.yaml
workflows/WF-003_enterprise_reasoning.json
src/reasoning/{__init__,prompt_loader,enterprise_llm,compliance_level,
               confidence,output_validator,wf003}.py
tests/test_sprint6.py
```
