-- SW-007/SW-008 batched extraction configuration (R-08: authored, never hardcoded).
-- plan() DERIVES maxPromptTokens and completionTarget from these — it solves both budgets
-- together against tpmBudget rather than taking two independently hand-tuned numbers.
UPDATE configuration.providers
SET settings = settings || jsonb_build_object(
  -- provider limits
  'tpmBudget',                30000,  -- tokens/min (input + output). Raise when your tier increases.
  'maxOutputTokens',          16384,  -- GPT-4o hard output ceiling
  'safetyMargin',              0.80,  -- never ride the TPM limit

  -- OUTPUT budgeting (this is what the prompt-only planner was missing)
  'extractionDensity',         0.30,  -- CALIBRATED from the live batch-2 failure (see note below)
  'tokensPerUnit',               55,  -- expected JSON tokens per knowledge unit
  'completionSafetyFactor',     2.0,  -- max_tokens = expected x this. Actual density can be
                                      -- this many times our estimate before truncating.

  -- batching
  'promptOverheadTokens',       800,  -- PR-001 body + system + JSON scaffolding
  'batchOverlapParagraphs',       3,  -- boundary-spanning statements seen whole
  'includeHeadingBreadcrumb',  true,  -- section ancestry as reference context
  'maxBatches',                 200,  -- runaway guard (throws rather than dropping content)
  'charsPerToken',                4,  -- estimation ratio (no tokenizer in the Code node)
  'maxPacingMs',              55000,  -- cap: n8n Wait >65s offloads to DB (unsupported here)

  -- SW-007 front-matter window (metadata is document-level; not batched)
  'metadataParagraphs',          80,
  'metadataScanPages',            5
)
WHERE kind = 'llm';

-- TUNING NOTE
-- If a batch throws finish_reason='length', the document is DENSER than extractionDensity assumes.
-- Raise extractionDensity (planner packs fewer paragraphs per batch) or raise
-- completionSafetyFactor (more output headroom). Both are safe; the first is usually correct.
-- SW-008 logs a DENSITY DRIFT warning when actual completion exceeds the budget by >1.5x.

-- ---------------------------------------------------------------------------
-- CALIBRATION NOTE — extractionDensity 0.12 -> 0.30
--
-- From the live run (CUBES SRS-2024, batch 2):
--     planned paragraphs        669
--     estimated prompt tokens   ~14,351
--     estimated completion      4,416
--     ACTUAL completion         8,832  = max_tokens  -> CENSORED (true demand was higher)
--
--     measured density >= 8832 / (669 x 55) = 0.240 KU/paragraph
--                      >= 2.0x the 0.12 default
--
-- Calibrated to 0.30: 25% above the observed floor, because (a) the censored measurement is a
-- LOWER bound, and (b) an SRS's normative sections are denser than its document mean.
--
-- Effect: ~426 paragraphs/batch (was 669, -36%); at the expected density the model sits at ~50%
-- of its output ceiling rather than AT it. The plan survives true density up to ~0.60 KU/para.
--
-- Why NOT just raise completionSafetyFactor: the safety factor absorbs VARIANCE around a correct
-- estimate. Using it to correct systematic BIAS would leave completionTarget, the drift detector
-- and the density telemetry all wrong, and would keep batches large and running at their ceiling.
-- ---------------------------------------------------------------------------
