-- Rollback for 0026_health_alert_center.sql (Sprint 8, S8-3)
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
-- NOTE: additive columns on monitoring.health_checks are dropped; the base
-- table (§142) is preserved. monitoring.alerts is dropped.
BEGIN;
DROP VIEW IF EXISTS admin.vw_alert_center;
DROP VIEW IF EXISTS admin.vw_health_center;
DROP TABLE IF EXISTS monitoring.alerts;
ALTER TABLE monitoring.health_checks
    DROP COLUMN IF EXISTS opened_at,
    DROP COLUMN IF EXISTS failure_count,
    DROP COLUMN IF EXISTS breaker_state;
COMMIT;
