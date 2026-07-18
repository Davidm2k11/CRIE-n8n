-- ============================================================================
-- CRIE Migration 0028 — ROLLBACK (§239)
-- Reverses 0028_benchmark_views.sql. Drops only the views this migration
-- created. Touches no Sprint 0-8 view. Order: dependents first.
-- ============================================================================

BEGIN;

DROP VIEW IF EXISTS admin.v_production_readiness_gate;
DROP VIEW IF EXISTS admin.v_acceptance_criteria_matrix;
DROP VIEW IF EXISTS admin.v_latency_latest_run;
DROP VIEW IF EXISTS admin.v_benchmark_target_summary;
DROP VIEW IF EXISTS admin.v_benchmark_latest_run;

DROP TABLE IF EXISTS monitoring.module_operational_validation;

COMMIT;
