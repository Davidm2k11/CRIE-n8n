-- Rollback 0018 — remove added columns/constraints/indexes (additive-only reversal).
DROP INDEX IF EXISTS repository.idx_knowledge_units_domain;
DROP INDEX IF EXISTS repository.idx_knowledge_units_capability;
DROP INDEX IF EXISTS repository.idx_knowledge_units_lifecycle_state;
ALTER TABLE repository.knowledge_units DROP CONSTRAINT IF EXISTS fk_knowledge_units_previous_version;
ALTER TABLE repository.knowledge_units DROP CONSTRAINT IF EXISTS chk_knowledge_units_category;
ALTER TABLE repository.knowledge_units DROP CONSTRAINT IF EXISTS chk_knowledge_units_lifecycle_state;
ALTER TABLE repository.knowledge_units
    DROP COLUMN IF EXISTS domain,
    DROP COLUMN IF EXISTS capability,
    DROP COLUMN IF EXISTS module,
    DROP COLUMN IF EXISTS feature,
    DROP COLUMN IF EXISTS authority_source,
    DROP COLUMN IF EXISTS authority_score,
    DROP COLUMN IF EXISTS quality_score,
    DROP COLUMN IF EXISTS lifecycle_state,
    DROP COLUMN IF EXISTS previous_version,
    DROP COLUMN IF EXISTS created_by,
    DROP COLUMN IF EXISTS change_reason;
