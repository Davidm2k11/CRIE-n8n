-- Rollback for 0024_admin_dashboard_views.sql (Sprint 8, S8-1/S8-4/S8-5)
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
BEGIN;
DROP VIEW IF EXISTS admin.vw_operational_kpis;
DROP VIEW IF EXISTS admin.vw_provider_dashboard;
DROP VIEW IF EXISTS admin.vw_review_dashboard;
DROP VIEW IF EXISTS admin.vw_benchmark_dashboard;
DROP VIEW IF EXISTS admin.vw_cost_intelligence;
DROP VIEW IF EXISTS admin.vw_ai_dashboard;
DROP VIEW IF EXISTS admin.vw_execution_explorer;
DROP VIEW IF EXISTS admin.vw_workflow_dashboard;
DROP VIEW IF EXISTS admin.vw_knowledge_analytics;
DROP VIEW IF EXISTS admin.vw_repository_dashboard;
DROP VIEW IF EXISTS admin.vw_main_dashboard;
COMMIT;
