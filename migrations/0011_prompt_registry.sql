-- 0011_prompt_registry.sql — Prompt Registry runtime tables (§11 registry, §172-175).
-- configuration.prompt_registry (0010) holds the manifest rows; this migration adds
-- the versioned-body cache table. Bodies themselves are authored in prompts/ and are
-- absent until their owning sprint; this table caches them at seed time when present.
CREATE TABLE IF NOT EXISTS configuration.prompt_versions (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prompt_id      TEXT NOT NULL,       -- PR-001..PR-008
    version        TEXT NOT NULL,
    system_prompt  TEXT,
    user_prompt    TEXT,
    schema         JSONB,
    model_settings JSONB,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_prompt_versions_id_version UNIQUE (prompt_id, version)
);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_prompt_id ON configuration.prompt_versions (prompt_id);
