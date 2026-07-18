-- Rollback 0017 — remove seeded reference data.
DELETE FROM configuration.authority_sources;
DELETE FROM configuration.knowledge_categories;
DELETE FROM configuration.configuration;
DELETE FROM configuration.providers;
DELETE FROM configuration.prompt_registry;
DELETE FROM configuration.workflow_registry;
