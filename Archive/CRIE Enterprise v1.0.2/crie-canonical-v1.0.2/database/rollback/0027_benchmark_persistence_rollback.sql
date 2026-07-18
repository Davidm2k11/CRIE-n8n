-- ============================================================================
-- CRIE Migration 0027 — ROLLBACK (§239)
-- Reverses 0027_benchmark_persistence.sql. Drops only the two tables this
-- migration created. Touches nothing else. Safe to run if 0027 applied.
-- ============================================================================

BEGIN;

DROP TABLE IF EXISTS monitoring.latency_history;
DROP TABLE IF EXISTS monitoring.benchmark_results;

COMMIT;
