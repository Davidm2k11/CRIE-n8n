-- ============================================================================
-- PR-001 v1.3 — constrain authoritySource to the canonical §439 nine
--
-- Runs as-is in the Supabase SQL Editor. No manual editing.
--
-- WHY: v1.2 never DEFINES authoritySource anywhere. Its only mention is the
-- language-exemption clause "keep product names, standard names, and section
-- titles exactly as they appear in the source", which the model reasonably reads
-- as the definition — so it emits section headings. Measured on the real corpus:
-- 962/962 knowledge units carry a non-canonical authoritySource ("CUBES CORPORATE
-- GOVERNANCE" 246, "Create New KPI" 107, "OCR Document" 83, "www.cubesplatform.com"
-- 20, Arabic section headings, …), and ZERO of the 53 distinct values match any of
-- the nine §439 authority sources. Because nothing valid was ever emitted, no
-- backfill is possible and re-ingestion is the only corrective path.
--
-- MINIMAL DELTA: v1.3 is v1.2 with exactly two textual edits —
--   1. an AUTHORITY SOURCE rules block inserted before CATEGORY, mirroring the
--      shape of the existing CATEGORY block;
--   2. the language-exemption clause reworded so it constrains LANGUAGE only and
--      no longer implies that section titles are authoritySource values.
-- The taxonomy (16 §438 values), the JSON schema, the output shape and the ocr
-- placeholder are UNCHANGED.
--
-- INTERPOLATION-SAFE BY CONSTRUCTION: the new body is derived from the stored
-- v1.2 row with replace(), so the chr()-built ocr placeholder is carried over
-- byte-for-byte and is never re-typed in this file. (§E of
-- docs/SRD_CHANGES_SINCE_SPEC.md: never send a literal double-brace sequence
-- through an n8n Postgres node — it is interpolated and destroyed. That rule
-- applies to COMMENTS in this file too, which is why the placeholder is described
-- here in words rather than written out.)
--
-- ADDITIVE: inserts v1.3 as a NEW ROW. v1.0–v1.2 remain for audit (baseline rule
-- 3). SW-008's loader (ORDER BY version DESC LIMIT 1, version is TEXT) selects
-- '1.3' because '1.3' > '1.2' lexically.
--
-- AUTHORITY: D6-approved. Paired with the SW-014 Repository Writer change that
-- persists authority_source / authority_score and FAILS LOUDLY on any value
-- outside the nine — so a prompt regression can no longer reach the database.
-- ============================================================================

INSERT INTO configuration.prompt_versions
    (prompt_id, version, system_prompt, user_prompt, schema, model_settings)
SELECT
    'PR-001',
    '1.3',

    -- system_prompt: IDENTICAL to v1.2.
    (SELECT system_prompt FROM configuration.prompt_versions
      WHERE prompt_id = 'PR-001' AND version = '1.2'),

    -- user_prompt: v1.2 with the two edits described above.
    replace(
      -- (1) reword the language exemption so it stops doubling as a definition.
      -- regexp_replace, not replace(): the clause spans a line break, and matching
      -- it literally makes the edit silently no-op on any whitespace or line-ending
      -- difference between this file and the stored row. The VERIFY block below
      -- asserts the old wording is actually gone — a literal match failed exactly
      -- this way on the first attempt.
      regexp_replace(
        (SELECT user_prompt FROM configuration.prompt_versions
          WHERE prompt_id = 'PR-001' AND version = '1.2'),
        $OLD$- "authoritySource" is exempt:.*?either way\.$OLD$,
        $NEW$- "authoritySource" is NOT translated: it is one of the nine fixed English
  values listed under AUTHORITY SOURCE below, and is never rendered in another
  language. It is a document-type label, not text copied from the document.$NEW$,
        'sg'
      ),

      -- (2) insert the AUTHORITY SOURCE block immediately before CATEGORY
      $ANCHOR$CATEGORY — assign exactly ONE.$ANCHOR$,
      $BLOCK$AUTHORITY SOURCE — assign exactly ONE. The allowed set is EXACTLY these 9 values.
Reproduce the spelling EXACTLY:

  Approved Product Specification - a signed-off specification of the product
  Official SRS                   - a formal software requirements specification
  Product Manual                 - end-user or administrator product documentation
  Training Material              - training, onboarding, or course content
  Architecture Guide             - architecture or design-level guidance
  Technical Design               - a detailed technical design document
  Release Notes                  - release, changelog, or version notes
  Previous Compliance Matrix     - an earlier completed compliance response
  Internal Notes                 - informal internal material

"authoritySource" describes THE DOCUMENT the paragraph came from — the same value
for every Knowledge Unit extracted from that document. It is NEVER a section
heading, a page title, a product name, a module name, a URL, or any other text
copied from the document body. If the document type is not evident, use
"Internal Notes". There is no other permitted value.

CATEGORY — assign exactly ONE.$BLOCK$
    ),

    -- schema: IDENTICAL to v1.2 (unchanged ontology + shape).
    (SELECT schema FROM configuration.prompt_versions
      WHERE prompt_id = 'PR-001' AND version = '1.2'),

    -- model_settings: IDENTICAL to v1.2.
    (SELECT model_settings FROM configuration.prompt_versions
      WHERE prompt_id = 'PR-001' AND version = '1.2')
ON CONFLICT (prompt_id, version) DO UPDATE
    SET system_prompt  = EXCLUDED.system_prompt,
        user_prompt    = EXCLUDED.user_prompt,
        schema         = EXCLUDED.schema,
        model_settings = EXCLUDED.model_settings;
-- Idempotent: re-running refreshes v1.3 from v1.2.


-- ============================================================================
-- VERIFY — the row SW-008 will load is v1.3, still carries the placeholder and
-- the full §438 taxonomy, now carries all nine §439 authority sources, and no
-- longer tells the model that section titles are authority sources.
-- ============================================================================
WITH selected AS (
    SELECT version, user_prompt
    FROM configuration.prompt_versions
    WHERE prompt_id = 'PR-001'
    ORDER BY version DESC
    LIMIT 1
)
SELECT
    version                                                              AS loaded_version,
    position(chr(123)||chr(123)||'ocr'||chr(125)||chr(125)
             IN user_prompt) > 0                                         AS placeholder_present,
    position('undefined' IN user_prompt) = 0                             AS no_literal_undefined,
    (user_prompt ~* 'PRESERVE THE SOURCE LANGUAGE')                      AS has_language_rule,
    (user_prompt ~* 'AUTHORITY SOURCE — assign exactly ONE')             AS has_authority_block,
    position('titles exactly as they appear' IN user_prompt) = 0         AS old_wording_removed,
    (SELECT count(*) FROM configuration.authority_sources a
      WHERE position(a.source IN user_prompt) > 0)                       AS canonical_authority_present,
    (SELECT count(*) FROM unnest(ARRAY[
        'Feature','Business Rule','Requirement','Limitation','Configuration',
        'Permission','Calculation','Workflow','Notification','Integration',
        'Reporting','Security','API','Architecture','Known Issue','Recommendation'
     ]) c WHERE position(c IN user_prompt) > 0)                          AS canonical_categories_present
FROM selected;
-- EXPECT: 1.3 | true | true | true | true | true | 9 | 16
