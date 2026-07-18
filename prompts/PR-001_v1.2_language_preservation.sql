-- ============================================================================
-- PR-001 v1.2 — add MANDATORY language preservation (Arabic/English)
--
-- Runs as-is in the Supabase SQL Editor. No manual editing.
--
-- WHY: Azure OCR extracts Arabic correctly, build-request() renders it, and the
-- OpenAI request payload contains the Arabic paragraphs — but the model RETURNS
-- Knowledge Unit statements in English. The translation happens INSIDE the LLM.
-- v1.1's prompt never instructs the model to keep the source language, so the
-- model silently normalises to English. v1.2 forbids that.
--
-- MINIMAL DELTA: v1.2 is v1.1 verbatim PLUS one "LANGUAGE" rules block. The
-- taxonomy (16 §438 values), the JSON schema, the output shape, and the ocr
-- placeholder are UNCHANGED. No workflow logic, repository object, category, or
-- schema is touched.
--
-- ADDITIVE: inserts v1.2 as a NEW ROW. v1.0 and v1.1 remain for audit. SW-008's
-- loader (ORDER BY version DESC LIMIT 1, version is TEXT) selects '1.2' because
-- '1.2' > '1.1' > '1.0' lexically.
--
-- INTERPOLATION-SAFE: the ocr placeholder is built from chr() codes so the
-- literal sequence "<<" never appears in this file; an n8n Postgres node cannot
-- destroy it. (chr(123)=open-brace, chr(125)=close-brace.)
-- ============================================================================

INSERT INTO configuration.prompt_versions
    (prompt_id, version, system_prompt, user_prompt, schema, model_settings)
SELECT
    'PR-001',
    '1.2',
    -- system_prompt: v1.1 verbatim + one sentence pinning source-language output.
    $SYS$You are a precise knowledge-extraction engine for enterprise compliance documents. You extract atomic business facts from structured OCR output. You never speculate, never summarise multiple facts into one unit, and never invent content that is not present in the source. You never translate: every extracted statement stays in the exact language of the source text. You return ONLY valid JSON — no prose, no markdown, no code fences.$SYS$,

    -- user_prompt: v1.1 verbatim, with a LANGUAGE block inserted before CATEGORY.
    -- The trailing "OCR CONTENT:" + placeholder is rebuilt with chr() so n8n cannot
    -- interpolate it.
    $PROMPT$Extract enterprise knowledge from the structured OCR content below.

RULES:
- One business fact per Knowledge Unit. Never combine multiple facts into one unit.
- Never summarise several facts into a single unit.
- Ignore formatting; preserve meaning.
- Extract only what the document states. Do not infer, speculate, or add knowledge.

LANGUAGE — PRESERVE THE SOURCE LANGUAGE. THIS IS MANDATORY.
- Write each "statement" in the EXACT language of the source paragraph it came from.
- If the source paragraph is in Arabic, the statement MUST be in Arabic.
- If the source paragraph is in English, the statement MUST be in English.
- NEVER translate. NEVER normalise or convert one language into another.
- NEVER rewrite Arabic into English, and NEVER rewrite English into Arabic.
- If a paragraph mixes languages, keep each part in its original language.
- "authoritySource" is exempt: keep product names, standard names, and section
  titles exactly as they appear in the source; do not translate them either way.

CATEGORY — assign exactly ONE. The allowed set is EXACTLY these 16 values.
Reproduce the spelling EXACTLY, including SPACES:

  Feature          - a described function or ability of the system
  Business Rule    - a policy or constraint governing behaviour  (NOTE THE SPACE)
  Requirement      - a stated obligation, including non-functional ones
                     (performance, availability, compliance obligations, SLAs)
  Limitation       - something the system does not do or cannot do
  Configuration    - a setting, parameter, or configurable option
  Permission       - access rights, roles, or authorisation
  Calculation      - a formula, derivation, or computation rule
  Workflow         - a sequence of steps or a process
  Notification     - an alert, message, or communication the system emits
  Integration      - an interaction with an external system
  Reporting        - a report, dashboard, or analytical output
  Security         - a security control or protection mechanism
  API              - an interface, endpoint, or contract
  Architecture     - structure, components, data model, or deployment topology
  Known Issue      - a defect, bug, or known problem  (NOTE THE SPACE)
  Recommendation   - advice, best practice, or operational guidance

There is NO "Other" category and no catch-all. If a fact does not fit any of the
16 values above, do NOT emit a Knowledge Unit for it.

Do NOT use any of these — they are RETIRED and will be REJECTED by the database:
  Capability, BusinessRule (without the space), DataModel, Performance,
  Compliance, Pricing, Support, Deployment, Roadmap, Other

For each unit, record the paragraph index it came from (and the page, when the
source document has native pagination) so evidence and citations can be traced
back to the source document.

Return ONLY valid JSON of this exact form, with no surrounding text:
{"knowledgeUnits":[{"statement":"","category":"","authoritySource":"","sourcePage":0,"sourceParagraph":0}]}

OCR CONTENT:
$PROMPT$ || chr(123)||chr(123)||'ocr'||chr(125)||chr(125) || $PROMPT2$
$PROMPT2$,

    -- schema: IDENTICAL to v1.1 (unchanged ontology + shape).
    (SELECT schema FROM configuration.prompt_versions
      WHERE prompt_id = 'PR-001' AND version = '1.1'),

    -- model_settings: IDENTICAL to v1.1.
    (SELECT model_settings FROM configuration.prompt_versions
      WHERE prompt_id = 'PR-001' AND version = '1.1')
ON CONFLICT (prompt_id, version) DO UPDATE
    SET system_prompt  = EXCLUDED.system_prompt,
        user_prompt    = EXCLUDED.user_prompt,
        schema         = EXCLUDED.schema,
        model_settings = EXCLUDED.model_settings;
-- Idempotent: re-running refreshes v1.2.


-- ============================================================================
-- VERIFY — the row SW-008 will load is v1.2, has the placeholder, has the
-- language block, and did NOT lose the taxonomy.
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
    (user_prompt ~* 'MUST be in Arabic')                                 AS has_arabic_rule,
    (SELECT count(*) FROM unnest(ARRAY[
        'Feature','Business Rule','Requirement','Limitation','Configuration',
        'Permission','Calculation','Workflow','Notification','Integration',
        'Reporting','Security','API','Architecture','Known Issue','Recommendation'
     ]) c WHERE position(c IN user_prompt) > 0)                          AS canonical_categories_present
FROM selected;
-- EXPECT: 1.2 | true | true | true | true | 16
