-- Rollback 0012.
DROP TABLE IF EXISTS monitoring.workflow_logs CASCADE;
DROP TABLE IF EXISTS monitoring.ai_requests CASCADE;
DROP TABLE IF EXISTS monitoring.execution_statistics CASCADE;
DROP TABLE IF EXISTS monitoring.health_checks CASCADE;
DROP TABLE IF EXISTS monitoring.benchmark_results CASCADE;
