-- Rollback 0015.
DROP FUNCTION IF EXISTS repository.repository_statistics();
DROP FUNCTION IF EXISTS repository.repository_version();
DROP FUNCTION IF EXISTS repository.repository_health();
DROP FUNCTION IF EXISTS repository.search_metadata(TEXT, TEXT);
DROP FUNCTION IF EXISTS repository.archive_document(UUID);
DROP FUNCTION IF EXISTS repository.create_document(TEXT, TEXT, TEXT);
DROP FUNCTION IF EXISTS repository.rebuild_embeddings(UUID);
