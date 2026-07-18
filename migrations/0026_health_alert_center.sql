-- =====================================================================
-- CRIE — Migration 0026_health_alert_center.sql
-- Sprint 8 (Administration) · Task S8-3
-- Spec: §568 (Health Center), §569 (Alert Center), §142 (health_checks),
--       §387 (Alert Thresholds).
-- Reconciliations: R-18 (circuit breaker = provider health state in the
--                  health_checks table; adapters short-circuit while Open).
--
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra. Unauthorized copying,
-- modification, distribution, or commercial use is prohibited without written
-- permission.
--
-- ADDITIVE ONLY. Adds monitoring.alerts (Alert Center persistence) and the
-- Health/Alert Center views. Extends the existing health_checks table (§142)
-- with an OPTIONAL circuit-breaker state column WITHOUT redefining it.
-- Rollback: 0026_health_alert_center_rollback.sql
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS admin;

-- --- R-18 circuit-breaker state on the existing §142 health_checks table ---
-- Additive columns only (all nullable / defaulted) — backward compatible.
ALTER TABLE monitoring.health_checks
    ADD COLUMN IF NOT EXISTS breaker_state   TEXT DEFAULT 'Closed',  -- Closed|Open|HalfOpen (R-18)
    ADD COLUMN IF NOT EXISTS failure_count   INTEGER DEFAULT 0,      -- rolling failures toward §387 threshold
    ADD COLUMN IF NOT EXISTS opened_at       TIMESTAMPTZ;            -- when breaker last opened

-- --- Alert Center persistence (§569) ---
CREATE TABLE IF NOT EXISTS monitoring.alerts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type    TEXT NOT NULL,     -- §569: RepositoryFailure|WorkflowFailure|ProviderFailure|
                                     --       HighCost|HighLatency|QueueBacklog|
                                     --       RepositoryHealthDrop|LowBenchmarkScore
    severity      TEXT NOT NULL,     -- §569: alerts SHALL include severity (Info|Warning|Critical)
    source        TEXT,              -- service / workflow / provider that raised it
    message       TEXT,
    context       JSONB,             -- structured detail (thresholds, observed values)
    correlation_id TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ,       -- NULL = open
    CONSTRAINT chk_alert_severity CHECK (severity IN ('Info','Warning','Critical'))
);

CREATE INDEX IF NOT EXISTS idx_alerts_type      ON monitoring.alerts (alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_open      ON monitoring.alerts (resolved_at) WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_created   ON monitoring.alerts (created_at);

COMMENT ON TABLE monitoring.alerts IS
    '§569 Alert Center persistence. Severity required. Raised by WF-005 / SW-028.';

-- ---------------------------------------------------------------------
-- §568 Health Center  →  admin.vw_health_center
-- Latest status per monitored service (n8n, Supabase, Google Drive, Azure
-- OCR, OpenAI, Claude, Embeddings, Storage, Queue System, Repository).
-- Health values: Healthy|Warning|Critical|Offline. Includes breaker state.
-- ---------------------------------------------------------------------
-- [DEPLOYMENT FIX — v1.0.1, same class as the 0024 audit]
-- monitoring.health_checks real columns are (component, state, detail,
-- checked_at) + the R-18 breaker columns this migration adds
-- (breaker_state, failure_count, opened_at). There is no .service/.status/
-- .latency. Repointed: .service->.component (aliased back to `service` to
-- preserve the output-column contract), .status->.state (aliased to
-- `status`), .latency->typed NULL (no v1 source). View name and output
-- columns unchanged (R-17 BI bindings unaffected).
CREATE OR REPLACE VIEW admin.vw_health_center AS
SELECT DISTINCT ON (hc.component)
    hc.component             AS service,
    hc.state                 AS status,   -- Healthy|Warning|Critical|Offline (§568)
    (NULL::numeric)          AS latency_ms,
    hc.breaker_state,        -- R-18 circuit-breaker state
    hc.failure_count,
    hc.checked_at
FROM monitoring.health_checks hc
ORDER BY hc.component, hc.checked_at DESC;

COMMENT ON VIEW admin.vw_health_center IS
    '§568 Health Center (latest per service) + R-18 breaker state. R-17.';

-- ---------------------------------------------------------------------
-- §569 Alert Center  →  admin.vw_alert_center
-- Open + recently-resolved alerts with severity.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW admin.vw_alert_center AS
SELECT
    id,
    alert_type,
    severity,
    source,
    message,
    context,
    correlation_id,
    created_at,
    resolved_at,
    (resolved_at IS NULL) AS is_open
FROM monitoring.alerts
WHERE resolved_at IS NULL
   OR resolved_at >= now() - INTERVAL '7 days';

COMMENT ON VIEW admin.vw_alert_center IS
    '§569 Alert Center (open + 7d resolved). R-17.';

COMMIT;
