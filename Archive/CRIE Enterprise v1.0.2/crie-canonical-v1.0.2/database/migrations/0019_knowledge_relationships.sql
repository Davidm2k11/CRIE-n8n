-- 0019_knowledge_relationships.sql — repository.knowledge_relationships (§239.1, §441).
CREATE TABLE IF NOT EXISTS repository.knowledge_relationships (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_ku_id      UUID NOT NULL,
    target_ku_id      UUID NOT NULL,
    relationship_type TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_knowledge_relationships_source
        FOREIGN KEY (source_ku_id) REFERENCES repository.knowledge_units (id) ON DELETE CASCADE,
    CONSTRAINT fk_knowledge_relationships_target
        FOREIGN KEY (target_ku_id) REFERENCES repository.knowledge_units (id) ON DELETE CASCADE,
    CONSTRAINT chk_knowledge_relationships_no_self CHECK (source_ku_id <> target_ku_id),
    CONSTRAINT chk_knowledge_relationships_type CHECK (relationship_type IN (
        'Supports','DependsOn','Requires','Extends','Overrides',
        'ConflictsWith','References','Implements','Replaces','DeprecatedBy'))
);
CREATE INDEX IF NOT EXISTS idx_knowledge_relationships_source_type
    ON repository.knowledge_relationships (source_ku_id, relationship_type);
