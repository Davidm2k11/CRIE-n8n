-- ============================================================================
-- CRIE Migration 0027 — Benchmark Persistence (Sprint 9, S9-3 / S9-8)
-- ----------------------------------------------------------------------------
-- ADDITIVE ONLY (§239, §239.1, R-15). This migration materializes the two
-- monitoring tables that the frozen spec NAMES but never physically defined:
--   * monitoring.benchmark_results   (§130/§3953, §196, §394-400)
--   * monitoring.latency_history     (§399 "Results SHALL be stored historically")
-- Same reconciliation pattern used for 0018-0023: implement schema Modules
-- already require but v1.0 gave no columns for. NO existing table, view, or
-- workflow is modified or redefined. No feature added; no numeric target
-- changed. Benchmark numeric targets (§196) stand exactly as written.
--
-- Depends on: monitoring schema (created pre-0018), Sprint 8 migrations
-- 0024-0026 (admin.* views). This migration adds tables only; it does not
-- touch admin.*, audit.*, repository.*, or configuration.*.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- monitoring.benchmark_results
-- One row per benchmark metric evaluation per run. Stores the measured value
-- and the frozen spec target so the Acceptance Criteria Matrix (§405) and
-- Production Readiness Gate (§406) can be computed as read-only views without
-- hardcoding targets anywhere in workflow logic.
-- ---------------------------------------------------------------------------
-- ---------------------------------------------------------------------------
-- [DEPLOYMENT RECONCILIATION — v1.0.1]
-- Migration 0012 shipped an unused PLACEHOLDER table of the same name with an
-- incompatible shape (dataset, metric, value, target, created_at) and NO
-- readers anywhere in the codebase. Because of `IF NOT EXISTS`, that placeholder
-- would otherwise survive and silently suppress the real definition below,
-- breaking every 0027-shape consumer (0024/0028 views, run_benchmark.py,
-- evaluate.py). Reconcile it here, in the additive Sprint 9 migration that
-- materializes the spec-named table (§130/§3953), so migrations 0001-0023 stay
-- frozen/untouched. Guarded: only drops the table if it exists WITHOUT the real
-- 0027 columns (i.e. only the empty placeholder), and never if real data is
-- present. No data is destroyed (the placeholder is never written to).
-- ---------------------------------------------------------------------------
DO $reconcile$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'monitoring' AND table_name = 'benchmark_results'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'monitoring' AND table_name = 'benchmark_results'
          AND column_name = 'metric_value'
    ) THEN
        IF (SELECT count(*) FROM monitoring.benchmark_results) > 0 THEN
            RAISE EXCEPTION
                'monitoring.benchmark_results exists with the legacy 0012 shape and '
                'contains data; refusing to auto-replace. Resolve manually.';
        END IF;
        DROP TABLE monitoring.benchmark_results;
    END IF;
END
$reconcile$;

CREATE TABLE IF NOT EXISTS monitoring.benchmark_results (
    id                BIGSERIAL PRIMARY KEY,
    run_id            UUID          NOT NULL,
    run_started_at    TIMESTAMPTZ   NOT NULL DEFAULT now(),
    -- Benchmark family per §394-400. Constrained to the frozen set of
    -- benchmark categories; no new categories may be introduced.
    benchmark         TEXT          NOT NULL
        CHECK (benchmark IN (
            'knowledge_extraction',  -- §394
            'retrieval',             -- §395
            'citation',              -- §396
            'hallucination',         -- §397
            'compliance_accuracy',   -- §398
            'latency',               -- §399
            'cost'                   -- §400
        )),
    metric            TEXT          NOT NULL,   -- e.g. 'f1', 'recall_at_10', 'mrr'
    metric_value      NUMERIC       NOT NULL,   -- measured value
    -- Frozen spec target for this metric (§196). NULL where the spec defines
    -- no explicit numeric gate (metric is measured/reported only).
    target_value      NUMERIC       NULL,
    -- Comparison direction: TRUE => higher is better (>= target),
    -- FALSE => lower is better (<= target). NULL where no target.
    higher_is_better  BOOLEAN       NULL,
    -- Derived pass/fail against the frozen target; NULL where no target.
    passed            BOOLEAN       NULL,
    spec_ref          TEXT          NOT NULL,   -- e.g. '§394', '§399'
    difficulty        TEXT          NULL        -- §392: Easy/Medium/Hard/Expert
        CHECK (difficulty IS NULL OR difficulty IN ('Easy','Medium','Hard','Expert')),
    dataset_category  TEXT          NULL,       -- §392 doc category
    notes             TEXT          NULL,
    recorded_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_benchmark_results_run
    ON monitoring.benchmark_results (run_id);
CREATE INDEX IF NOT EXISTS ix_benchmark_results_benchmark
    ON monitoring.benchmark_results (benchmark, metric);
CREATE INDEX IF NOT EXISTS ix_benchmark_results_recorded
    ON monitoring.benchmark_results (recorded_at DESC);

COMMENT ON TABLE monitoring.benchmark_results IS
    'Sprint 9 (0027): benchmark metric evaluations. Materializes §130/§3953 '
    'monitoring.benchmark_results named but not physically defined in v1.0. '
    'Additive per §239.1/R-15. Targets sourced from §196 (unchanged).';

-- ---------------------------------------------------------------------------
-- monitoring.latency_history
-- Per-stage latency measurements, stored historically per §399. Feeds the
-- Latency Benchmark (§399) and the Performance Benchmark comparison (§197).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS monitoring.latency_history (
    id                BIGSERIAL PRIMARY KEY,
    run_id            UUID          NOT NULL,
    stage             TEXT          NOT NULL
        CHECK (stage IN (
            'document_registration', -- §399
            'ocr',                   -- §399/§197
            'knowledge_extraction',  -- §399/§197
            'chunking',              -- §399/§197
            'embedding',             -- §399/§197
            'retrieval',             -- §399/§197
            'reasoning',             -- §399/§197
            'google_sheets_export',  -- §399/§197
            'end_to_end'             -- §399
        )),
    duration_seconds  NUMERIC       NOT NULL,
    target_seconds    NUMERIC       NULL,       -- §197 Maximum Targets
    passed            BOOLEAN       NULL,        -- duration <= target
    document_count    INTEGER       NULL,        -- for load-test correlation (§401)
    recorded_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_latency_history_run
    ON monitoring.latency_history (run_id);
CREATE INDEX IF NOT EXISTS ix_latency_history_stage
    ON monitoring.latency_history (stage, recorded_at DESC);

COMMENT ON TABLE monitoring.latency_history IS
    'Sprint 9 (0027): historical per-stage latency (§399). Targets from §197 '
    '(unchanged). Additive per §239.1/R-15.';

COMMIT;
