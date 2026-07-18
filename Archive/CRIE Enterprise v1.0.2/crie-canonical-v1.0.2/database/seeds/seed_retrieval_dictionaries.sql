-- =============================================================================
-- CRIE — seed_retrieval_dictionaries.sql
-- Seeds configuration.synonyms / configuration.acronyms (migration 0021) and
-- the authority reference from the authored YAML source of truth (R-08).
-- These are the values consumed by SW-016 normalization/expansion (§453-455)
-- and by authority ranking (§439/§464).
--
-- This file is the SQL projection of config/retrieval.yaml + config/authority.yaml.
-- The YAML remains the source of truth; regenerate this on config change (§236).
-- License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
-- =============================================================================

BEGIN;

-- --- §444 synonyms (0021: configuration.synonyms) ---------------------------
INSERT INTO configuration.synonyms (id, term, synonym) VALUES
  (gen_random_uuid(), 'kpi',        'metric'),
  (gen_random_uuid(), 'kpi',        'performance indicator'),
  (gen_random_uuid(), 'initiative', 'program'),
  (gen_random_uuid(), 'initiative', 'strategic initiative'),
  (gen_random_uuid(), 'dashboard',  'reporting'),
  (gen_random_uuid(), 'dashboard',  'analytics')
ON CONFLICT DO NOTHING;

-- --- §445 acronyms (0021: configuration.acronyms) ---------------------------
INSERT INTO configuration.acronyms (id, acronym, expansion) VALUES
  (gen_random_uuid(), 'SRS', 'software requirements specification'),
  (gen_random_uuid(), 'KPI', 'key performance indicator'),
  (gen_random_uuid(), 'SLA', 'service level agreement'),
  (gen_random_uuid(), 'RBAC', 'role based access control'),
  (gen_random_uuid(), 'SSO', 'single sign on')
ON CONFLICT DO NOTHING;

-- --- §454 metadata expansions (topic graph; stored as synonyms rows tagged) --
-- Metadata expansion topics reuse the synonyms table with a topic convention;
-- if a dedicated table is preferred it is an additive, compliant choice.
INSERT INTO configuration.synonyms (id, term, synonym) VALUES
  (gen_random_uuid(), 'dashboard',     'visualization'),
  (gen_random_uuid(), 'risk register', 'risk'),
  (gen_random_uuid(), 'risk register', 'compliance'),
  (gen_random_uuid(), 'risk register', 'audit')
ON CONFLICT DO NOTHING;

-- --- §439 / R-16 authority reference (canonical 9-source table) --------------
-- Seeded into the authority reference table used by ranking (§464).
-- Table name follows the configuration schema convention; scores configurable.
INSERT INTO configuration.authority_sources (id, source, score) VALUES
  (gen_random_uuid(), 'Approved Product Specification', 100),
  (gen_random_uuid(), 'Official SRS',                     98),
  (gen_random_uuid(), 'Product Manual',                   95),
  (gen_random_uuid(), 'Training Material',                90),
  (gen_random_uuid(), 'Architecture Guide',               88),
  (gen_random_uuid(), 'Technical Design',                 85),
  (gen_random_uuid(), 'Release Notes',                    80),
  (gen_random_uuid(), 'Previous Compliance Matrix',       65),
  (gen_random_uuid(), 'Internal Notes',                   40)
ON CONFLICT DO NOTHING;

COMMIT;
