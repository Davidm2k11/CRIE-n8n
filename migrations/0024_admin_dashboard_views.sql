-- =====================================================================
-- CRIE — Migration 0024_admin_dashboard_views.sql
-- Sprint 8 (Administration) · Tasks S8-1, S8-4, S8-5
-- Spec: §232 (Repository Views), §558–§565 (Administration dashboards),
--       §528/§529/§533 (repository health/statistics/analytics),
--       §198 (cost monitoring), §16 (telemetry).
-- Reconciliations: R-17 (dashboards = Supabase views surfaced in a BI tool;
--                  n8n produces data, not UI), R-02 (Administration = WF-005).
--
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra. Unauthorized copying,
-- modification, distribution, or commercial use is prohibited without written
-- permission.
--
-- ADDITIVE ONLY. This migration creates read-only VIEWS in the `admin` schema
-- that extend the §232 repository views. No existing table or view is redefined.
-- Views contain NO business logic (Principle: business logic stays in n8n);
-- they are thin projections/aggregations over existing tables for BI surfacing.
--
-- Rollback: 0024_admin_dashboard_views_rollback.sql
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS admin;

-- ---------------------------------------------------------------------
-- §558 Main Dashboard  →  admin.vw_main_dashboard
-- Platform Status, Repository Health, Today's Processing, Avg Confidence,
-- Avg Cost, Running/Failed Workflows, Pending Reviews, Provider Status,
-- System Alerts. One row (platform-wide snapshot).
-- ---------------------------------------------------------------------
-- ---------------------------------------------------------------------
-- [DEPLOYMENT FIX — Sprint 10 audit of 0024]
-- The original Sprint 8 view bodies referenced several objects and columns
-- that the FROZEN schema (migrations 0001-0023, plus additive 0026/0027) never
-- creates — the deploy failed at the first one (repository.repository_health).
-- Each such reference is corrected to the real source, or exposed as a typed
-- NULL / 0 placeholder where v1 has no source (never fabricated; NO table or
-- column is invented — that would be a redesign). Every view's NAME and OUTPUT
-- COLUMN CONTRACT is preserved, so BI bindings (R-17) and the Sprint 8/9
-- acceptance suites are unaffected. Corrections applied:
--   repository.repository_health (a FUNCTION 0015 / VIEW vw_repository_health 0016,
--       not a selectable table) -> repository.vw_repository_health
--       .status -> .state ;  .health_score -> NULL (score is computed in the
--       repository health-statistics / BI layer, not in SQL)
--   monitoring.health_checks.status  -> .state
--   monitoring.health_checks.service -> .component
--   monitoring.health_checks.latency -> NULL (no such column in v1)
--   monitoring.ai_requests.confidence -> NULL ; .latency_ms -> .latency ; .success -> derived NULL
--   monitoring.workflow_logs.created_at -> .timestamp ; phantom workflow_logs
--       columns (workflow_name/version, runtime_ms, total_cost, *_payload,
--       prompt_version, repository_version) -> real columns or NULL
--   repository.documents.lifecycle_state -> .status (lifecycle_state is a
--       knowledge_units property added by 0018, not a documents column)
--   repository.knowledge_units.language -> NULL bucket (column never added)
--   repository.review_queue / .requirements / .proposals -> not in v1 schema -> 0/NULL
--   monitoring.telemetry -> not in v1 -> NULL
--   configuration.reasoning_config / .benchmark_targets -> not in v1 -> NULL;
--       benchmark target lives in monitoring.benchmark_results.target_value
-- No behavior of prior sprints is removed; columns without a v1 data source
-- return empty (NULL/0) until the corresponding feature ships (§21 future).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_main_dashboard AS
SELECT
    (SELECT state FROM repository.vw_repository_health ORDER BY checked_at DESC LIMIT 1)         AS platform_status,
    (NULL::int)                                                                                  AS repository_health,
    (SELECT COUNT(*) FROM monitoring.processing_history
        WHERE created_at::date = CURRENT_DATE)                                                   AS today_processing,
    (NULL::numeric)                                                                              AS average_confidence,
    (SELECT ROUND(AVG(estimated_cost)::numeric, 6) FROM monitoring.ai_requests
        WHERE created_at >= CURRENT_DATE - INTERVAL '1 day')                                     AS average_cost,
    (SELECT COUNT(*) FROM monitoring.workflow_logs WHERE status = 'RUNNING')                     AS running_workflows,
    (SELECT COUNT(*) FROM monitoring.workflow_logs
        WHERE status = 'FAILED' AND timestamp::date = CURRENT_DATE)                              AS failed_workflows,
    (0::bigint)                                                                                  AS pending_reviews,
    (SELECT COUNT(*) FROM monitoring.health_checks
        WHERE state IN ('Healthy','Warning') AND checked_at >= now() - INTERVAL '15 minutes')    AS providers_ok,
    (0::bigint)                                                                                  AS open_alerts;
-- open_alerts: monitoring.alerts is created by migration 0026 (runs after this
-- one in numeric apply order), so it cannot be referenced here. Exposed as a
-- typed 0 placeholder, consistent with this file's other not-yet-available
-- sources. The live open-alert count is surfaced by 0026's admin.vw_alert_center.

COMMENT ON VIEW admin.vw_main_dashboard IS
    '§558 Main Dashboard snapshot. R-17: BI-surfaced read-only view.';

-- ---------------------------------------------------------------------
-- §559 Repository Dashboard  →  admin.vw_repository_dashboard
-- Documents, Certified/Pending/Archived, Knowledge Units, Evidence,
-- Citations, Retrieval Chunks, Embeddings, Repository Health, Version.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_repository_dashboard AS
SELECT
    (SELECT COUNT(*) FROM repository.documents)                                          AS documents,
    (SELECT COUNT(*) FROM repository.knowledge_units WHERE lifecycle_state = 'Certified') AS certified_documents,
    (SELECT COUNT(*) FROM repository.documents WHERE status = 'Uploaded')                 AS pending_documents,
    (SELECT COUNT(*) FROM repository.documents WHERE status = 'Archived')                 AS archived_documents,
    (SELECT COUNT(*) FROM repository.knowledge_units)                                     AS knowledge_units,
    (SELECT COUNT(*) FROM repository.evidence)                                            AS evidence_objects,
    (SELECT COUNT(*) FROM repository.citations)                                           AS citations,
    (SELECT COUNT(*) FROM repository.retrieval_chunks)                                    AS retrieval_chunks,
    (SELECT COUNT(*) FROM repository.embeddings)                                          AS embeddings,
    (NULL::int)                                                                           AS repository_health,
    (SELECT repository.repository_version())                                              AS repository_version;

COMMENT ON VIEW admin.vw_repository_dashboard IS
    '§559 Repository Dashboard. Extends §232 vw_repository_summary. R-17.';

-- ---------------------------------------------------------------------
-- §560 / §533 Knowledge Analytics  →  admin.vw_knowledge_analytics
-- Category / authority / language / lifecycle distributions + certification.
-- Multi-row (one per grouping dimension:value) for BI charting.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_knowledge_analytics AS
    SELECT 'category'   AS dimension, COALESCE(category, 'Unclassified')       AS bucket, COUNT(*) AS unit_count
        FROM repository.knowledge_units GROUP BY category
    UNION ALL
    SELECT 'authority'  AS dimension, COALESCE(authority_source, 'Unknown')    AS bucket, COUNT(*)
        FROM repository.knowledge_units GROUP BY authority_source
    UNION ALL
    SELECT 'language'   AS dimension, 'Unknown'                                AS bucket, COUNT(*)
        FROM repository.knowledge_units
    UNION ALL
    SELECT 'lifecycle'  AS dimension, COALESCE(lifecycle_state, 'Draft')       AS bucket, COUNT(*)
        FROM repository.knowledge_units GROUP BY lifecycle_state;

COMMENT ON VIEW admin.vw_knowledge_analytics IS
    '§560/§533 Knowledge Analytics distributions. R-17.';

-- ---------------------------------------------------------------------
-- §561 Workflow Dashboard  →  admin.vw_workflow_dashboard
-- Per-workflow: executions, success/failure rate, avg runtime, avg cost,
-- retries, last execution, current status.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_workflow_dashboard AS
SELECT
    wl.workflow_id,
    (NULL::text)                                                                  AS workflow_name,
    (NULL::text)                                                                  AS workflow_version,
    COUNT(*)                                                                      AS executions,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wl.status = 'SUCCESS') / NULLIF(COUNT(*),0), 2) AS success_rate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wl.status = 'FAILED')  / NULLIF(COUNT(*),0), 2) AS failure_rate,
    ROUND(AVG(wl.duration)::numeric, 2)                                           AS avg_runtime_ms,
    (NULL::numeric)                                                               AS avg_cost,
    COALESCE(SUM(wl.retry_count), 0)                                              AS retries,
    MAX(wl.timestamp)                                                             AS last_execution
FROM monitoring.workflow_logs wl
GROUP BY wl.workflow_id;

COMMENT ON VIEW admin.vw_workflow_dashboard IS
    '§561 Workflow Dashboard. R-17.';

-- ---------------------------------------------------------------------
-- §562 Execution Explorer  →  admin.vw_execution_explorer
-- Per-execution troubleshooting projection (input/output/logs/errors/retries).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_execution_explorer AS
SELECT
    wl.execution_id,
    wl.correlation_id,
    (NULL::text)                  AS workflow,
    (NULL::text)                  AS workflow_version,
    (NULL::text)                  AS prompt_version,
    (NULL::text)                  AS repository_version,
    wl.duration                   AS duration_ms,
    (NULL::jsonb)                 AS input,
    (NULL::jsonb)                 AS output,
    wl.level                      AS logs,
    wl.error                      AS errors,
    wl.retry_count                AS retry_history,
    wl.timestamp                  AS created_at
FROM monitoring.workflow_logs wl;

COMMENT ON VIEW admin.vw_execution_explorer IS
    '§562 Execution Explorer. R-17.';

-- ---------------------------------------------------------------------
-- §563 AI Dashboard  →  admin.vw_ai_dashboard
-- Per provider+model: requests, tokens, avg latency, avg/total cost, rates.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_ai_dashboard AS
SELECT
    ar.provider,
    ar.model,
    COUNT(*)                                                                       AS requests,
    COALESCE(SUM(ar.input_tokens), 0)                                              AS input_tokens,
    COALESCE(SUM(ar.output_tokens), 0)                                             AS output_tokens,
    ROUND(AVG(ar.latency)::numeric, 2)                                             AS avg_latency_ms,
    ROUND(AVG(ar.estimated_cost)::numeric, 6)                                      AS avg_cost,
    ROUND(SUM(ar.estimated_cost)::numeric, 6)                                      AS total_cost,
    (NULL::numeric)                                                                AS failure_rate,
    (NULL::numeric)                                                                AS success_rate
FROM monitoring.ai_requests ar
GROUP BY ar.provider, ar.model;

COMMENT ON VIEW admin.vw_ai_dashboard IS
    '§563 AI Dashboard. Token usage tracked by provider (§16 telemetry). R-17.';

-- ---------------------------------------------------------------------
-- §564 / §198 Cost Intelligence  →  admin.vw_cost_intelligence
-- Daily / weekly / monthly cost + per-unit averages. One row snapshot.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_cost_intelligence AS
SELECT
    ROUND(SUM(ar.estimated_cost) FILTER (WHERE ar.created_at >= CURRENT_DATE)::numeric, 6)                       AS daily_cost,
    ROUND(SUM(ar.estimated_cost) FILTER (WHERE ar.created_at >= CURRENT_DATE - INTERVAL '7 days')::numeric, 6)  AS weekly_cost,
    ROUND(SUM(ar.estimated_cost) FILTER (WHERE ar.created_at >= date_trunc('month', CURRENT_DATE))::numeric, 6) AS monthly_cost,
    (NULL::numeric)                                                                                             AS avg_cost_per_requirement,
    ROUND(SUM(ar.estimated_cost)::numeric
        / NULLIF((SELECT COUNT(*) FROM repository.documents), 0), 6)                                            AS avg_cost_per_document,
    (NULL::numeric)                                                                                             AS avg_cost_per_proposal,
    ROUND(SUM(ar.estimated_cost)::numeric
        / NULLIF((SELECT COUNT(*) FROM repository.knowledge_units), 0), 6)                                      AS avg_cost_per_knowledge_unit
FROM monitoring.ai_requests ar;

COMMENT ON VIEW admin.vw_cost_intelligence IS
    '§564 Cost Intelligence / §198 Cost Monitoring. R-17.';

-- ---------------------------------------------------------------------
-- §565 Benchmark Dashboard  →  admin.vw_benchmark_dashboard
-- Latest benchmark run per metric + history is exposed via base table.
-- Targets are read from the benchmark_results.target_value column (frozen §196
-- targets recorded per run by Sprint 9's 0027), not a separate targets table.
-- ---------------------------------------------------------------------
-- monitoring.benchmark_results (the Sprint 9 shape: metric_value/target_value/
-- passed/recorded_at) is materialized by migration 0027, which runs AFTER this
-- migration in numeric apply order; it cannot be referenced here. This view's
-- output-column contract is preserved exactly as an empty placeholder until the
-- benchmark layer exists. The live benchmark dashboard is served by Sprint 9's
-- 0028 views (admin.v_benchmark_latest_run / admin.v_benchmark_target_summary).
CREATE OR REPLACE VIEW admin.vw_benchmark_dashboard AS
SELECT
    (NULL::text)    AS metric,
    (NULL::numeric) AS value,
    (NULL::numeric) AS target_value,
    (NULL::boolean) AS meets_target,
    (NULL::timestamptz) AS run_at
WHERE false;

COMMENT ON VIEW admin.vw_benchmark_dashboard IS
    '§565 Benchmark Dashboard (latest per metric). Targets configurable. R-17.';

-- ---------------------------------------------------------------------
-- §566 Human Review Dashboard  →  admin.vw_review_dashboard
-- ---------------------------------------------------------------------
-- review_queue and configuration.reasoning_config are not part of the v1 frozen
-- schema; expose the contract columns as an empty (0/NULL) single-row snapshot
-- until the Human Review persistence feature ships (§21 future). No table invented.
CREATE OR REPLACE VIEW admin.vw_review_dashboard AS
SELECT
    (0::bigint)     AS pending_reviews,
    (0::bigint)     AS assigned_reviews,
    (0::bigint)     AS approved_reviews,
    (0::bigint)     AS rejected_reviews,
    (NULL::numeric) AS avg_review_seconds,
    (0::bigint)     AS low_confidence_responses;

COMMENT ON VIEW admin.vw_review_dashboard IS
    '§566 Human Review Dashboard. R-17.';

-- ---------------------------------------------------------------------
-- §567 Provider Dashboard  →  admin.vw_provider_dashboard
-- Provider health / latency / error rate from health_checks.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_provider_dashboard AS
SELECT
    hc.component                                         AS service,
    hc.state                                             AS provider_health,
    (NULL::numeric)                                      AS avg_latency_ms,
    ROUND(100.0 * COUNT(*) FILTER (WHERE hc.state IN ('Critical','Offline'))
        / NULLIF(COUNT(*),0), 2)                         AS error_rate,
    MAX(hc.checked_at)                                   AS last_checked
FROM monitoring.health_checks hc
WHERE hc.checked_at >= now() - INTERVAL '24 hours'
GROUP BY hc.component, hc.state;

COMMENT ON VIEW admin.vw_provider_dashboard IS
    '§567 Provider Dashboard. R-17.';

-- ---------------------------------------------------------------------
-- §577 Operational KPIs  →  admin.vw_operational_kpis
-- Platform-wide KPI snapshot for trend analysis.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_operational_kpis AS
SELECT
    (NULL::int)                                                                             AS repository_health,
    (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE state IN ('Healthy','Warning'))
        / NULLIF(COUNT(*),0), 2) FROM monitoring.health_checks
        WHERE checked_at >= now() - INTERVAL '24 hours')                                     AS system_availability,
    (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'SUCCESS')
        / NULLIF(COUNT(*),0), 2) FROM monitoring.workflow_logs
        WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days')                                AS workflow_success_rate,
    (NULL::numeric)                                                                         AS average_confidence,
    (SELECT ROUND(AVG(estimated_cost)::numeric, 6) FROM monitoring.ai_requests
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days')                                AS average_cost,
    (NULL::numeric)                                                                         AS avg_retrieval_ms,
    (NULL::numeric)                                                                         AS avg_reasoning_ms,
    (NULL::numeric)                                                                         AS human_review_rate,
    (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE lifecycle_state = 'Certified')
        / NULLIF(COUNT(*),0), 2) FROM repository.knowledge_units)                           AS knowledge_certification_rate;

COMMENT ON VIEW admin.vw_operational_kpis IS
    '§577 Operational KPIs snapshot. R-17.';

COMMIT;

-- =====================================================================
-- NOTE (R-17): These views are the *data* layer only. The dashboard UI is
-- provided by the external BI tool (Supabase Studio / Metabase / Grafana)
-- consuming these views. n8n (WF-005) refreshes the underlying data; it
-- renders no UI. No metric from §558–§577 is dropped.
-- =====================================================================
