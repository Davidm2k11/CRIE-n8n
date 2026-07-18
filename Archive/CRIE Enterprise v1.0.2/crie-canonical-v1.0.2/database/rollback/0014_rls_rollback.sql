-- Rollback 0014 — drop policies and disable RLS.
DO $$
DECLARE t TEXT;
BEGIN
  FOR t IN SELECT unnest(ARRAY['documents','metadata','knowledge_units','evidence',
                               'citations','retrieval_chunks','embeddings'])
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS p_service_all ON repository.%I;', t);
    EXECUTE format('DROP POLICY IF EXISTS p_read_repository ON repository.%I;', t);
    EXECUTE format('ALTER TABLE repository.%I DISABLE ROW LEVEL SECURITY;', t);
  END LOOP;
END $$;
