# Platform Foundation Architecture

Platform Foundation (Module 01) provides the runtime services every business
module depends on, established before any business logic (§10–20). On the
frozen n8n + Supabase stack these services are realized as authored
configuration, canonical JSON contracts, a workflow/prompt registry, and the
Startup Validation workflow.

## Runtime layers (§300)

```
Environment Variables  (secrets, per-environment; §314)
        ↓
Configuration Registry (YAML authored → configuration.* cache; R-08)
        ↓
Workflow Configuration (config.* reads; no hardcoding, Principle 7)
        ↓
Node Configuration
        ↓
Execution
```

## Services

**Configuration Registry (§12).** Ten domain YAML files are the source of truth;
the `configuration.*` tables (Sprint 2) are the runtime cache. Every configurable
value is read from the registry.

**Prompt Registry (§13, §172–175).** All prompts loaded by ID + version; never
embedded in workflows (§608). Canonical catalog is the eight PR-001…PR-008
(R-04). Every update creates a new version; workflows pin a version. Bodies are
authored in their owning sprints.

**Secrets Management (§14, §321–324).** Secrets live only in n8n credentials /
env vars / cloud secret managers. Only adapter nodes access them; business nodes
never do. Rotation requires no workflow change.

**Logging (§15).** Structured JSON only (free text prohibited); required fields
per the `structured_log` contract; levels INFO/WARNING/ERROR/CRITICAL. Persisted
to `monitoring.workflow_logs` (Sprint 2).

**Telemetry (§16, Principle 8).** Every AI request records tokens, model,
provider, latency, cost per the `telemetry` contract → `monitoring.ai_requests`.

**Event Bus (§17).** Event-driven orchestration; workflows are triggered by
events rather than calling each other directly where an event is appropriate.

**Health Monitoring (§18, §366).** Each component reports Healthy / Warning /
Critical / Offline per the `health_status` contract → `monitoring.health_checks`.

**Error Handling (§19).** Errors classified Recoverable / Business / Fatal /
Unexpected; every workflow returns the `workflow_error` contract.

**Provider Adapter Layer (§316–320).** OCR / LLM / embedding / storage sit behind
adapters; workflows talk only to adapters; swapping a provider is config-only
(§360). Every adapter returns the provider-independent `adapter_error` contract
(Module 37), honors the timeout policy (Module 38) and exponential-backoff retry
(Module 39, §214). Interface fixed in `schemas/contracts/adapter_interface.yaml`;
concrete adapters built in Sprints 3/6/7.

**Workflow Registry (§152, §213).** Canonical inventory of every WF/SW/UT ID,
type, owning sprint, and build status. IDs never change after publication (§634).

## Standard workflow pattern (§159 / §212)

Every workflow follows: Trigger → Initialize → Validate Input → Execute →
Validate Output → Persist → Log → Return Result. No workflow bypasses
validation. Each carries the §213 metadata block (name, version, description,
owner, dependencies, retry strategy, timeout, inputs, outputs) and ends with the
§216 execution summary consumed by Monitoring.

## Startup Validation (R-14)

n8n has no boot phase that can refuse to start, so the §326 "application startup"
lifecycle is realized as the `UT-007_Startup_Validation` utility workflow, run on
deploy and on schedule. It loads config + env, runs the §327 checks, would ping
providers via the adapters, and writes a health record. Invalid configuration ⇒
health `Critical` + alert, and downstream master workflows refuse to run against
it. Valid ⇒ health `Healthy`, which is the Sprint 1 exit gate.
