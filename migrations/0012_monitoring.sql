-- 0012_monitoring.sql — monitoring.* tables (§229). Monitoring data is never mixed
-- with repository data (§229).
CREATE TABLE IF NOT EXISTS monitoring.workflow_logs (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id    TEXT,
    execution_id   TEXT,
    node_id        TEXT,
    correlation_id TEXT,
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration       NUMERIC,
    status         TEXT,
    level          TEXT,
    error          TEXT,
    retry_count    INTEGER,
    provider       TEXT,
    model          TEXT
);
CREATE TABLE IF NOT EXISTS monitoring.ai_requests (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    correlation_id TEXT,
    provider       TEXT,
    model          TEXT,
    input_tokens   INTEGER,
    output_tokens  INTEGER,
    latency        NUMERIC,
    estimated_cost NUMERIC,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS monitoring.execution_statistics (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow       TEXT,
    execution_id   TEXT,
    status         TEXT,
    duration       NUMERIC,
    cost           NUMERIC,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS monitoring.health_checks (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    component      TEXT NOT NULL,
    state          TEXT NOT NULL,     -- Healthy | Warning | Critical | Offline
    detail         JSONB,
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS monitoring.benchmark_results (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dataset        TEXT,
    metric         TEXT,
    value          NUMERIC,
    target         NUMERIC,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_workflow_logs_correlation_id ON monitoring.workflow_logs (correlation_id);
CREATE INDEX IF NOT EXISTS idx_ai_requests_correlation_id   ON monitoring.ai_requests (correlation_id);
CREATE INDEX IF NOT EXISTS idx_health_checks_component      ON monitoring.health_checks (component);
