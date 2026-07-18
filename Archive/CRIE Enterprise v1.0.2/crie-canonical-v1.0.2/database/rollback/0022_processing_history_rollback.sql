-- Rollback 0022.
DROP TRIGGER IF EXISTS trg_processing_history_append_only ON monitoring.processing_history;
DROP TABLE IF EXISTS monitoring.processing_history CASCADE;
-- deny_mutation() is shared with 0023; drop only if audit tables are gone.
DROP FUNCTION IF EXISTS monitoring.deny_mutation();
