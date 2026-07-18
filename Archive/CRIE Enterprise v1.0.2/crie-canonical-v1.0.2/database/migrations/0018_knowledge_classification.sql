-- 0018_knowledge_classification.sql — ADD columns to repository.knowledge_units
-- (§239.1, R-15). Purely additive: no column is redefined or dropped.
ALTER TABLE repository.knowledge_units
    ADD COLUMN IF NOT EXISTS domain           TEXT,          -- §433
    ADD COLUMN IF NOT EXISTS capability       TEXT,          -- §434
    ADD COLUMN IF NOT EXISTS module           TEXT,          -- §435
    ADD COLUMN IF NOT EXISTS feature          TEXT,          -- §436
    ADD COLUMN IF NOT EXISTS authority_source TEXT,          -- §439
    ADD COLUMN IF NOT EXISTS authority_score  INTEGER,       -- §439 (configurable)
    ADD COLUMN IF NOT EXISTS quality_score    NUMERIC,       -- §511 (0.00-1.00)
    ADD COLUMN IF NOT EXISTS lifecycle_state  TEXT DEFAULT 'Draft',  -- §518
    ADD COLUMN IF NOT EXISTS previous_version UUID,          -- §519 lineage (self-ref)
    ADD COLUMN IF NOT EXISTS created_by       TEXT,          -- §519
    ADD COLUMN IF NOT EXISTS change_reason    TEXT;          -- §519

-- Self-reference for version lineage (§519).
ALTER TABLE repository.knowledge_units
    DROP CONSTRAINT IF EXISTS fk_knowledge_units_previous_version;
ALTER TABLE repository.knowledge_units
    ADD CONSTRAINT fk_knowledge_units_previous_version
    FOREIGN KEY (previous_version) REFERENCES repository.knowledge_units (id);

-- category constrained to the canonical §438 enum (R-05). The value list must
-- match configuration.knowledge_categories and database/seeds/knowledge_categories.yaml.
ALTER TABLE repository.knowledge_units
    DROP CONSTRAINT IF EXISTS chk_knowledge_units_category;
ALTER TABLE repository.knowledge_units
    ADD CONSTRAINT chk_knowledge_units_category
    CHECK (category IS NULL OR category IN (
        'Feature','Business Rule','Requirement','Limitation','Configuration',
        'Permission','Calculation','Workflow','Notification','Integration',
        'Reporting','Security','API','Architecture','Known Issue','Recommendation'));

-- lifecycle_state constrained to §518 states.
ALTER TABLE repository.knowledge_units
    DROP CONSTRAINT IF EXISTS chk_knowledge_units_lifecycle_state;
ALTER TABLE repository.knowledge_units
    ADD CONSTRAINT chk_knowledge_units_lifecycle_state
    CHECK (lifecycle_state IN ('Draft','Validated','Certified','Deprecated','Archived'));

CREATE INDEX IF NOT EXISTS idx_knowledge_units_domain          ON repository.knowledge_units (domain);
CREATE INDEX IF NOT EXISTS idx_knowledge_units_capability      ON repository.knowledge_units (capability);
CREATE INDEX IF NOT EXISTS idx_knowledge_units_lifecycle_state ON repository.knowledge_units (lifecycle_state);
