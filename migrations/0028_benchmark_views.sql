-- ============================================================================
-- CRIE Migration 0028 — Benchmark & Readiness Views (Sprint 9, S9-3/S9-8)
-- ----------------------------------------------------------------------------
-- ADDITIVE ONLY (§239, R-15, R-17). Adds read-only views under the existing
-- `admin` schema (created in Sprint 8) that surface Sprint 9 benchmark data to
-- the BI layer. This preserves the Sprint 8 contract: dashboards are admin.*
-- Supabase views; n8n produces data, not UI (R-17). BI-platform agnostic —
-- Metabase / Power BI / Grafana consume these views identically; no
-- architectural change is required to swap the BI product.
--
-- NO existing view is redefined or dropped. These are NEW view names only.
-- Depends on: 0027 (monitoring.benchmark_results, monitoring.latency_history).
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- admin.v_benchmark_latest_run
-- The most recent benchmark run's metrics with pass/fail vs frozen targets.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.v_benchmark_latest_run AS
WITH latest AS (
    SELECT run_id
    FROM monitoring.benchmark_results
    ORDER BY run_started_at DESC
    LIMIT 1
)
SELECT
    br.run_id,
    br.run_started_at,
    br.benchmark,
    br.metric,
    br.metric_value,
    br.target_value,
    br.higher_is_better,
    br.passed,
    br.spec_ref,
    br.difficulty,
    br.dataset_category
FROM monitoring.benchmark_results br
JOIN latest USING (run_id)
ORDER BY br.benchmark, br.metric;

COMMENT ON VIEW admin.v_benchmark_latest_run IS
    'Sprint 9 (0028): latest benchmark run vs §196 targets. R-17 BI contract.';

-- ---------------------------------------------------------------------------
-- admin.v_benchmark_target_summary
-- One row per gated benchmark metric: measured, target, and pass state, using
-- only rows from the latest run. Drives the Benchmark Report (§196).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.v_benchmark_target_summary AS
SELECT
    benchmark,
    metric,
    spec_ref,
    metric_value,
    target_value,
    higher_is_better,
    passed
FROM admin.v_benchmark_latest_run
WHERE target_value IS NOT NULL
ORDER BY benchmark, metric;

COMMENT ON VIEW admin.v_benchmark_target_summary IS
    'Sprint 9 (0028): gated benchmark metrics only (§196/§394-400).';

-- ---------------------------------------------------------------------------
-- admin.v_latency_latest_run
-- Latest per-stage latency vs §197 targets.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.v_latency_latest_run AS
WITH latest AS (
    SELECT run_id
    FROM monitoring.latency_history
    ORDER BY recorded_at DESC
    LIMIT 1
)
SELECT
    lh.run_id,
    lh.stage,
    lh.duration_seconds,
    lh.target_seconds,
    lh.passed,
    lh.document_count,
    lh.recorded_at
FROM monitoring.latency_history lh
JOIN latest USING (run_id)
ORDER BY lh.stage;

COMMENT ON VIEW admin.v_latency_latest_run IS
    'Sprint 9 (0028): latest per-stage latency vs §197/§399. R-17 BI contract.';

-- ---------------------------------------------------------------------------
-- monitoring.module_operational_validation
-- Operational validation state (§199/§390) for §405 modules whose quality is
-- REPORTED rather than numerically gated by §394-400 (e.g. Administration:
-- §400 cost is reported, not gated). Populated by the run / deployment; the
-- matrix reads pass/fail from here instead of a fabricated numeric target.
-- Additive; no existing table touched.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS monitoring.module_operational_validation (
    module        TEXT PRIMARY KEY,
    passed        BOOLEAN NOT NULL,
    basis         TEXT NOT NULL,          -- e.g. 'health+telemetry+audit (§199)'
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE monitoring.module_operational_validation IS
    'Sprint 9 (0028): operational validation (§199/§390) for §405 modules not '
    'numerically gated by §394-400. No fabricated numeric target.';

-- ---------------------------------------------------------------------------
-- admin.v_acceptance_criteria_matrix  (§405)
-- Maps each spec module to Pass/Fail. A module passes only when every gated
-- benchmark metric mapped to it passed in the latest run. Module->benchmark
-- mapping follows §405 module list and the §394-400 benchmark families.
-- "No module may remain partially complete" (§405) is enforced by requiring
-- bool_and over all gated metrics for the module.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.v_acceptance_criteria_matrix AS
WITH module_map AS (
    -- (module_label, family) association per §405. 'latency' and the §394-400
    -- families are numerically gated; 'cost' is operationally validated.
    SELECT * FROM (VALUES
        ('Platform Foundation', 'latency'),
        ('Knowledge Ingestion', 'knowledge_extraction'),
        ('Repository',          'knowledge_extraction'),
        ('Retrieval',           'retrieval'),
        ('Reasoning',           'hallucination'),
        ('Reasoning',           'compliance_accuracy'),
        ('Output',              'citation'),
        ('Administration',      'cost')
    ) AS m(module_label, family)
),
-- Numeric gates: §394-400 benchmark rows (latest run) that have a target.
gated_bench AS (
    SELECT benchmark AS family, passed
    FROM admin.v_benchmark_latest_run
    WHERE target_value IS NOT NULL
),
-- Latency gates: §197 per-stage rows (latest run) that have a target.
gated_latency AS (
    SELECT 'latency'::TEXT AS family, passed
    FROM admin.v_latency_latest_run
    WHERE target_seconds IS NOT NULL
),
gated AS (
    SELECT * FROM gated_bench
    UNION ALL
    SELECT * FROM gated_latency
),
-- Operational validation for reported-only families (cost).
operational AS (
    SELECT 'cost'::TEXT AS family, passed
    FROM monitoring.module_operational_validation
    WHERE module = 'Administration'
),
signal AS (
    SELECT family, passed FROM gated
    UNION ALL
    SELECT family, passed FROM operational
)
SELECT
    mm.module_label AS module,
    CASE
        WHEN count(s.passed) = 0 THEN 'No Data'
        WHEN bool_and(s.passed)  THEN 'Pass'
        ELSE 'Fail'
    END AS required
FROM module_map mm
LEFT JOIN signal s USING (family)
GROUP BY mm.module_label
ORDER BY mm.module_label;

COMMENT ON VIEW admin.v_acceptance_criteria_matrix IS
    'Sprint 9 (0028): §405 Acceptance Criteria Matrix. Pass iff all gated '
    'metrics for the module passed in the latest run. No partial completion.';

-- ---------------------------------------------------------------------------
-- admin.v_production_readiness_gate  (§406)
-- Single-row gate. all_benchmarks_met is computed from the latest run; the
-- remaining operational criteria (defects, UAT, backup/recovery, monitoring,
-- cost tracking) are surfaced from the readiness checklist table if present,
-- otherwise reported as 'Deployment-Confirmed' placeholders are NOT emitted —
-- instead they read from monitoring/admin state already established in prior
-- sprints. This view reports benchmark + defect + UAT status only from data;
-- deployment-side sign-offs (backup/recovery tested) are confirmed at Sprint
-- 10 / deployment and are intentionally left as explicit NULL => 'Pending'
-- rather than fabricated as passed.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.v_production_readiness_gate AS
WITH bench AS (
    SELECT
        CASE WHEN count(*) = 0 THEN NULL ELSE bool_and(passed) END AS all_met
    FROM (
        SELECT passed FROM admin.v_benchmark_latest_run
        WHERE target_value IS NOT NULL
        UNION ALL
        SELECT passed FROM admin.v_latency_latest_run
        WHERE target_seconds IS NOT NULL
    ) all_gated
),
matrix AS (
    SELECT
        CASE
            WHEN count(*) FILTER (WHERE required = 'Fail')   > 0 THEN FALSE
            WHEN count(*) FILTER (WHERE required = 'No Data')> 0 THEN NULL
            ELSE TRUE
        END AS all_modules_pass
    FROM admin.v_acceptance_criteria_matrix
)
SELECT
    b.all_met                         AS all_benchmark_targets_met,   -- §406 ✓1
    m.all_modules_pass                AS acceptance_matrix_pass,      -- §405
    -- Operational criteria are deployment-verified (§199/§406). Reported as
    -- NULL (=> 'Pending deployment verification') until confirmed in the
    -- target environment; never fabricated as passed in the build env.
    NULL::BOOLEAN                     AS no_critical_defects,         -- §406 ✓2
    NULL::BOOLEAN                     AS no_high_severity_defects,    -- §406 ✓3
    NULL::BOOLEAN                     AS uat_approved,                -- §406 ✓4/§404
    NULL::BOOLEAN                     AS documentation_complete,      -- §406 ✓5
    NULL::BOOLEAN                     AS backup_tested,               -- §406 ✓6
    NULL::BOOLEAN                     AS recovery_tested,             -- §406 ✓7
    NULL::BOOLEAN                     AS monitoring_operational,      -- §406 ✓8
    NULL::BOOLEAN                     AS cost_tracking_operational,   -- §406 ✓9
    CASE
        WHEN b.all_met IS TRUE AND m.all_modules_pass IS TRUE
            THEN 'Benchmark gate: PASS (deployment sign-offs pending)'
        WHEN b.all_met IS FALSE OR m.all_modules_pass IS FALSE
            THEN 'Benchmark gate: FAIL — do not deploy'
        ELSE 'Benchmark gate: NO DATA'
    END AS gate_status
FROM bench b CROSS JOIN matrix m;

COMMENT ON VIEW admin.v_production_readiness_gate IS
    'Sprint 9 (0028): §406 Production Readiness Gate. Benchmark/matrix computed '
    'from data; deployment sign-offs reported as Pending (verified Sprint 10).';

COMMIT;
