-- 0014_rls.sql — Row Level Security (§235). Workflow execution uses Service Role.
-- Future user access uses dedicated policies (§235). RLS is enabled per
-- security.rowLevelSecurity (config-driven, default true).
ALTER TABLE repository.documents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE repository.metadata         ENABLE ROW LEVEL SECURITY;
ALTER TABLE repository.knowledge_units  ENABLE ROW LEVEL SECURITY;
ALTER TABLE repository.evidence         ENABLE ROW LEVEL SECURITY;
ALTER TABLE repository.citations        ENABLE ROW LEVEL SECURITY;
ALTER TABLE repository.retrieval_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE repository.embeddings       ENABLE ROW LEVEL SECURITY;

-- Service Role has full access (workflow execution). In Supabase the service role
-- bypasses RLS by default; these policies make read intent explicit and provide a
-- baseline for future user policies.
DO $$
DECLARE t TEXT;
BEGIN
  FOR t IN
    SELECT unnest(ARRAY[
      'documents','metadata','knowledge_units','evidence',
      'citations','retrieval_chunks','embeddings'])
  LOOP
    EXECUTE format(
      'DROP POLICY IF EXISTS p_service_all ON repository.%I;', t);
    EXECUTE format(
      'CREATE POLICY p_service_all ON repository.%I FOR ALL TO service_role USING (true) WITH CHECK (true);', t);
    EXECUTE format(
      'DROP POLICY IF EXISTS p_read_repository ON repository.%I;', t);
    EXECUTE format(
      'CREATE POLICY p_read_repository ON repository.%I FOR SELECT TO authenticated USING (true);', t);
  END LOOP;
END $$;
