-- Rollback 0023 — drop audit tables (append-only triggers drop with the tables).
DROP TABLE IF EXISTS audit.prompt_changes CASCADE;
DROP TABLE IF EXISTS audit.configuration_changes CASCADE;
DROP TABLE IF EXISTS audit.workflow_changes CASCADE;
DROP TABLE IF EXISTS audit.repository_changes CASCADE;
