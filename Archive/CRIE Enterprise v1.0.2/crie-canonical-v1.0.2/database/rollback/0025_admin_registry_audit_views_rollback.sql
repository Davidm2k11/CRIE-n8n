-- Rollback for 0025_admin_registry_audit_views.sql (Sprint 8, S8-6/S8-7)
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
BEGIN;
DROP VIEW IF EXISTS admin.vw_audit_center;
DROP VIEW IF EXISTS admin.vw_configuration_dashboard;
DROP VIEW IF EXISTS admin.vw_prompt_registry_dashboard;
COMMIT;
