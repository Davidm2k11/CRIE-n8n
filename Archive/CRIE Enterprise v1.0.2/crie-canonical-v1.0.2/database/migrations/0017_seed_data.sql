-- 0017_seed_data.sql — Seed the runtime cache from the authored YAML (§236, R-08).
-- No business knowledge is seeded (§236). This migration is the SQL landing point;
-- the actual values are pushed by scripts/setup/seed_configuration.py, which reads
-- configuration/*.yaml (source of truth) and populates these tables. Re-running the
-- seed re-syncs config WITHOUT source edits (config is adjusted in YAML only).
--
-- The seed set (§236): Configuration, Default Prompt Registry, Default Providers,
-- Workflow Registry, plus the authority-source (§439,R-16) and knowledge-category
-- (§438,R-05) reference data.
--
-- Category reference (§438, R-05) — the 16 frozen values. Kept in sync with
-- database/seeds/knowledge_categories.yaml and the 0018 CHECK constraint.
INSERT INTO configuration.knowledge_categories (category) VALUES
    ('Feature'),('Business Rule'),('Requirement'),('Limitation'),
    ('Configuration'),('Permission'),('Calculation'),('Workflow'),
    ('Notification'),('Integration'),('Reporting'),('Security'),
    ('API'),('Architecture'),('Known Issue'),('Recommendation')
ON CONFLICT (category) DO NOTHING;

-- Authority sources (§439, R-16) — seeded here as the v1 defaults; the seed script
-- overwrites from retrieval.yaml authoritySources so scores stay config-driven.
INSERT INTO configuration.authority_sources (source, score) VALUES
    ('Approved Product Specification', 100),
    ('Official SRS', 98),
    ('Product Manual', 95),
    ('Training Material', 90),
    ('Architecture Guide', 88),
    ('Technical Design', 85),
    ('Release Notes', 80),
    ('Previous Compliance Matrix', 65),
    ('Internal Notes', 40)
ON CONFLICT (source) DO UPDATE SET score = EXCLUDED.score;

-- configuration.configuration / providers / prompt_registry / workflow_registry
-- are populated by scripts/setup/seed_configuration.py from the YAML source of
-- truth (R-08). This file intentionally does not hardcode those values, to avoid
-- a second source of truth (§627).
