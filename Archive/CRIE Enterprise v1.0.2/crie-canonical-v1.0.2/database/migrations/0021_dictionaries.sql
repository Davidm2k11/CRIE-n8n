-- 0021_dictionaries.sql — configuration.synonyms / acronyms (§239.1, §444-445).
-- Seeded from configuration (R-08): database/seeds/dictionaries.yaml is the
-- authored source; scripts/setup/seed_configuration.py loads it. Adjustable
-- without editing SQL or workflows. Used by normalization (§453)/expansion (§455).
CREATE TABLE IF NOT EXISTS configuration.synonyms (
    id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    term    TEXT NOT NULL,
    synonym TEXT NOT NULL,
    CONSTRAINT uq_synonyms_pair UNIQUE (term, synonym)
);
CREATE TABLE IF NOT EXISTS configuration.acronyms (
    id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    acronym   TEXT NOT NULL,
    expansion TEXT NOT NULL,
    CONSTRAINT uq_acronyms_pair UNIQUE (acronym, expansion)
);
CREATE INDEX IF NOT EXISTS idx_synonyms_term    ON configuration.synonyms (term);
CREATE INDEX IF NOT EXISTS idx_acronyms_acronym ON configuration.acronyms (acronym);
