-- =====================================================================
-- CRIE — Migration 0025_admin_registry_audit_views.sql
-- Sprint 8 (Administration) · Tasks S8-6, S8-7
-- Spec: §570 (Prompt Registry Dashboard), §571 (Configuration Dashboard),
--       §572 (Audit Center), §230/§239.1-0023 (immutable audit.* tables).
-- Reconciliations: R-17 (views surfaced in BI; n8n produces data, not UI).
--
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra. Unauthorized copying,
-- modification, distribution, or commercial use is prohibited without written
-- permission.
--
-- ADDITIVE ONLY. Read-only views over the existing Prompt Registry,
-- Configuration Registry, and immutable audit.* tables. No table redefined.
-- Rollback: 0025_admin_registry_audit_views_rollback.sql
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS admin;

-- ---------------------------------------------------------------------
-- §570 Prompt Registry Dashboard  →  admin.vw_prompt_registry_dashboard
-- Prompt ID, Version, Status, Owner, Last Updated, Usage Count,
-- Avg Runtime, Avg Confidence, Benchmark Status.
-- (Rollback is a WF-005 operation, not a view; see §570 note.)
-- ---------------------------------------------------------------------
-- ---------------------------------------------------------------------
-- [DEPLOYMENT FIX — v1.0.1, same class as the 0024 audit]
-- The original Sprint 8 body referenced columns/objects the frozen schema
-- (0001-0023) never creates. Corrected to real sources, or typed NULL/0
-- placeholders where v1 has no source. No object/column invented; the view
-- NAME and OUTPUT-COLUMN CONTRACT are preserved (R-17 BI bindings unaffected):
--   configuration.prompt_registry real columns are (prompt_id, version, name,
--     category, latest, updated_at, id) — there is no .status/.owner/
--     .benchmark_status -> exposed as typed NULL placeholders.
--   monitoring.ai_requests has no prompt_id/latency_ms/confidence columns
--     (real: latency, estimated_cost, tokens; no per-prompt linkage in v1) ->
--     usage_count/avg_runtime_ms/avg_confidence exposed as 0/NULL until the
--     prompt-usage linkage feature ships (§21 future).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_prompt_registry_dashboard AS
SELECT
    p.prompt_id,
    p.version,
    (NULL::text)      AS status,
    (NULL::text)      AS owner,
    p.updated_at      AS last_updated,
    (0::bigint)       AS usage_count,
    (NULL::numeric)   AS avg_runtime_ms,
    (NULL::numeric)   AS avg_confidence,
    (NULL::text)      AS benchmark_status
FROM configuration.prompt_registry p;

COMMENT ON VIEW admin.vw_prompt_registry_dashboard IS
    '§570 Prompt Registry Dashboard (PR-001..PR-008). R-17.';

-- ---------------------------------------------------------------------
-- §571 Configuration Dashboard  →  admin.vw_configuration_dashboard
-- Current Environment, Enabled Providers, Feature Flags, Config Version,
-- Secrets Status (presence only — never value), recent Config Changes count.
-- Secrets are surfaced as boolean "configured" only (never the value).
-- ---------------------------------------------------------------------
-- [DEPLOYMENT FIX — v1.0.1] configuration.platform_config / provider_config /
-- feature_flags / secrets_registry are NOT part of the frozen v1 schema (no
-- migration creates them). The real config store is the single KV table
-- configuration.configuration (domain, key, value). Environment/config_version
-- are read from it by key; provider enablement lives in configuration.providers
-- (settings JSONB). Feature flags and a secrets-presence registry have no v1
-- source -> exposed as typed NULL/0 placeholders (never inventing a table).
-- audit.configuration_changes is real (0023) and kept as-is. View name and
-- output-column contract unchanged.
CREATE OR REPLACE VIEW admin.vw_configuration_dashboard AS
SELECT
    (SELECT value #>> '{}' FROM configuration.configuration WHERE key = 'environment' LIMIT 1)  AS current_environment,
    (SELECT string_agg(kind, ', ') FROM configuration.providers
        WHERE COALESCE((settings ->> 'enabled')::boolean, false) = true)                         AS enabled_providers,
    (NULL::text)                                                                                AS feature_flags,
    (SELECT value #>> '{}' FROM configuration.configuration WHERE key = 'config_version' LIMIT 1) AS configuration_version,
    (0::bigint)                                                                                 AS secrets_configured,
    (0::bigint)                                                                                 AS secrets_missing,
    (SELECT COUNT(*) FROM audit.configuration_changes
        WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days')                                    AS config_changes_7d;

COMMENT ON VIEW admin.vw_configuration_dashboard IS
    '§571 Configuration Dashboard. Secrets exposed as presence only, never value. R-17.';

-- ---------------------------------------------------------------------
-- §572 Audit Center  →  admin.vw_audit_center
-- Unified read-only projection across the four immutable audit.* tables
-- (§230; columns per §344 via 0023). Repository/Workflow/Prompt/Config
-- changes, user actions, certification events, review decisions.
-- The audit.* tables are append-only (0023 enforces revoked UPDATE/DELETE +
-- trigger). This view NEVER writes.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_audit_center AS
    SELECT event_id, 'repository'    AS audit_domain, event_type, "user", timestamp, object_type, object_id, changes
        FROM audit.repository_changes
    UNION ALL
    SELECT event_id, 'workflow'      AS audit_domain, event_type, "user", timestamp, object_type, object_id, changes
        FROM audit.workflow_changes
    UNION ALL
    SELECT event_id, 'configuration' AS audit_domain, event_type, "user", timestamp, object_type, object_id, changes
        FROM audit.configuration_changes
    UNION ALL
    SELECT event_id, 'prompt'        AS audit_domain, event_type, "user", timestamp, object_type, object_id, changes
        FROM audit.prompt_changes;

COMMENT ON VIEW admin.vw_audit_center IS
    '§572 Audit Center. Immutable append-only audit.* (§230/0023). Read-only. R-17.';

COMMIT;
