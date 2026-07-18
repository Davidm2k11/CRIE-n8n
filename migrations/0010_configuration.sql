-- 0010_configuration.sql — configuration.* runtime-cache tables (§228, R-08).
-- These are the RUNTIME CACHE of configuration; the authored source of truth is
-- the YAML under configuration/. Values are populated by 0017 (seed/sync), never
-- authored directly here.
CREATE TABLE IF NOT EXISTS configuration.configuration (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain     TEXT NOT NULL,        -- e.g. providers, retrieval, reasoning...
    key        TEXT NOT NULL,        -- dotted path e.g. retrieval.topK
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_configuration_domain_key UNIQUE (domain, key)
);

CREATE TABLE IF NOT EXISTS configuration.providers (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind       TEXT NOT NULL,        -- ocr | llm | embedding | storage
    settings   JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_providers_kind UNIQUE (kind)
);

CREATE TABLE IF NOT EXISTS configuration.prompt_registry (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prompt_id     TEXT NOT NULL,     -- PR-001..PR-008 (R-04)
    version       TEXT,
    name          TEXT,
    category      TEXT,
    latest        BOOLEAN NOT NULL DEFAULT false,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_prompt_registry_id_version UNIQUE (prompt_id, version)
);

CREATE TABLE IF NOT EXISTS configuration.workflow_registry (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id   TEXT NOT NULL,     -- WF-xxx | SW-xxx | UT-xxx
    name          TEXT,
    type          TEXT,              -- master | shared | utility
    status        TEXT,              -- built | planned
    owned_by_sprint INTEGER,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_workflow_registry_id UNIQUE (workflow_id)
);

-- Authority-source reference (§439, R-16). Scores are config-driven (seeded from
-- retrieval.yaml authoritySources); adjustable without editing SQL.
CREATE TABLE IF NOT EXISTS configuration.authority_sources (
    id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source   TEXT NOT NULL,
    score    INTEGER NOT NULL,
    CONSTRAINT uq_authority_sources_source UNIQUE (source)
);

-- Knowledge category reference (§438, R-05). The 16 frozen values; seeded from
-- database/seeds/knowledge_categories.yaml. The CHECK constraint in 0018 must
-- match this set.
CREATE TABLE IF NOT EXISTS configuration.knowledge_categories (
    category TEXT PRIMARY KEY
);
