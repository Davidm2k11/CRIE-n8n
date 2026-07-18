-- 0023_audit_columns.sql — concrete columns for audit.* + immutability (§239.1, §230, §344).
-- Columns per the §344 audit record; append-only via a trigger and revoked
-- UPDATE/DELETE grants. Audit records are never deleted (§230).
DO $$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY[
      'repository_changes','workflow_changes',
      'configuration_changes','prompt_changes'])
  LOOP
    EXECUTE format($f$
      CREATE TABLE IF NOT EXISTS audit.%I (
        event_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        event_type  TEXT NOT NULL,
        "user"      TEXT,
        timestamp   TIMESTAMPTZ NOT NULL DEFAULT now(),
        object_type TEXT,
        object_id   TEXT,
        changes     JSONB
      );$f$, t);

    -- Immutability: block UPDATE/DELETE (reuse monitoring.deny_mutation from 0022).
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_append_only ON audit.%I;', t, t);
    EXECUTE format($f$
      CREATE TRIGGER trg_%s_append_only
      BEFORE UPDATE OR DELETE ON audit.%I
      FOR EACH ROW EXECUTE FUNCTION monitoring.deny_mutation();$f$, t, t);

    -- Revoke UPDATE/DELETE from all roles (defense in depth).
    EXECUTE format('REVOKE UPDATE, DELETE ON audit.%I FROM PUBLIC;', t);
  END LOOP;
END $$;
