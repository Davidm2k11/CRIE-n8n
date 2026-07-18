# CRIE Security Review

_Deliverable: S10-1 (§203, §330–§350, §403). Sprint 10, v1.0.0._
_Authoritative spec: CRIE Enterprise Specification v1.1.1._

Security review of the canonical repository against the §203 pre-production
checklist, the §330–§350 security architecture, and the §403 security tests.
Items verifiable in the build environment are marked accordingly; items that are
environmental are marked as deployment-confirmed with the control that enforces
them.

## 1. §203 pre-production security checklist

| Item | Status | Evidence / control |
|---|---|---|
| RLS enabled | Enforced by schema | `database/migrations/0014_rls.sql`; verified by `tests/integration/test_database.py` (RLS enabled; Service Role policy present, §235) |
| Secrets encrypted | Enforced by design | Secrets only in env/allowed stores (§321–324/§608); `.env` git-ignored; n8n credential store encrypted (`N8N_ENCRYPTION_KEY`) |
| HTTPS enabled | Deployment-confirmed | Production compose sets `N8N_PROTOCOL=https`, secure cookie; TLS terminates at ingress (Deployment Guide) |
| Service keys protected | Enforced by design | `.env.example` carries **no values** (§682); keys supplied per environment; validator checks presence, never prints values |
| Audit logging enabled | Enforced by schema | Audit events/records/retention (§343–§345); immutable records, ≥365-day retention |
| Provider keys rotated | Deployment-confirmed | Rotation is an operational task; adapters read keys from env so rotation needs no code change |
| Repository access restricted | Enforced by design | Access only via Repository API / Writer / Retrieval (§339); direct workflow SQL prohibited |

## 2. §330–§333 principles & data handling

Least privilege, zero trust, defense in depth, secure-by-default, separation,
auditability, and traceability are reflected in the layered design (§331):
network → authentication → authorization → workflow → repository → AI → audit.
The tooling image runs as a non-root user. Data classification (Public /
Internal / Confidential / Restricted, §332) drives access policy, and sensitive
data (customer names, keys, credentials, internal architecture, financial data,
pre-approval compliance responses) is not exposed to AI unless required (§333).

## 3. §334–§339 authn / authz / repository

Phase-1 platform authentication only; RBAC roles (§336/§337) defined for a future
phase. Every provider authenticates via API key / OAuth / service account; no
anonymous providers (§335). Only certified, non-archived knowledge is retrievable
(§338); deleted objects remain recoverable (archive-not-delete, §530/§531);
repository access is confined to the sanctioned components (§339).

## 4. §340–§342 AI security

LLMs receive only the Context Package, prompt, and variables; never raw PDFs, the
whole repository, keys, configuration, secrets, or internal logs (§340). Prompt
injection is mitigated: uploaded document content is treated as data and cannot
modify the system prompt, configuration, or workflow logic (§341). Every request
uses an isolated Context Package; knowledge does not leak across executions
(§342). These are exercised by the security harness (Section 6).

## 5. §343–§348 audit & compliance

Audited events (§343) include document upload, repository update, prompt update,
configuration change, workflow modification, AI request, human review, and
archive. Each audit record carries the §344 fields and is immutable; retention is
≥365 days (§345). Compliance objectives (§346) — traceability, explainability,
auditability, evidence preservation, version history — hold; every Compliance
Result answers the §347 explainability questions and supports the full §348
reverse-trace chain.

## 6. §403 security testing

The Sprint 9 security harness (`tests/regression/security_harness.py`) and the
Sprint 6 reasoning suite exercise the AI-security controls; the results are part
of the acceptance gate. Verified in this review:

- Prompt-injection content in an uploaded document does not alter system
  behavior (§341) — security harness passes on secure fixtures.
- Repository isolation blocks cross-tenant/cross-execution access (§342) —
  Sprint 9 `test_repository_isolation_blocks_cross_tenant` passes.
- Provider failure trips the circuit breaker and requests fail fast (§384) —
  Sprint 9 `test_provider_failure_trips_circuit` passes.
- Unexpected file types are rejected — Sprint 9 `test_unexpected_file_type_rejected`
  passes.

## 7. Repository hygiene findings (fixed in Sprint 10)

The audit found no secret material committed (`.env.example` is value-free). A
packaging defect was corrected: the v0.10.0 archive had bundled a **copy of
itself** (`crie-canonical-v0_10_0_tar.gz`) inside the repository tree; it is
excluded from the v1.0.0 bundle and ignored via `.gitignore`. No other sensitive
data, credentials, or tokens were found in tracked files.

## 8. Disposition

No Critical or High security defects were found in the delivered artifacts. The
build-verifiable §203 items and the §403 controls pass. The environmental items
(HTTPS termination, key rotation cadence, live audit retention) are enforced by
the documented controls and confirmed on the target deployment as part of the
§406 gate.
