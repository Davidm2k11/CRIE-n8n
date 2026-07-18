-- 0020_semantic_tags.sql — repository.knowledge_tags (§239.1, §443).
CREATE TABLE IF NOT EXISTS repository.knowledge_tags (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_unit_id UUID NOT NULL,
    tag               TEXT NOT NULL,
    CONSTRAINT fk_knowledge_tags_knowledge_units
        FOREIGN KEY (knowledge_unit_id) REFERENCES repository.knowledge_units (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_knowledge_tags_tag ON repository.knowledge_tags (tag);
