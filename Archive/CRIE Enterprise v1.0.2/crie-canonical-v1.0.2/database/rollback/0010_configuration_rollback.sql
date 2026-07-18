-- Rollback 0010.
DROP TABLE IF EXISTS configuration.configuration CASCADE;
DROP TABLE IF EXISTS configuration.providers CASCADE;
DROP TABLE IF EXISTS configuration.prompt_registry CASCADE;
DROP TABLE IF EXISTS configuration.workflow_registry CASCADE;
DROP TABLE IF EXISTS configuration.authority_sources CASCADE;
DROP TABLE IF EXISTS configuration.knowledge_categories CASCADE;
