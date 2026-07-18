/**
 * CRIE — Module 13 Ingestion Sub-Workflows (SW-001 … SW-015)
 * Sprint 3 · Knowledge Ingestion · targets v0.4.0
 *
 * Source of truth: CRIE Enterprise Specification v1.1 (frozen).
 *   Canonical node contracts: §240–255 (Module 13).
 *   WF-001 execution + failure policy: §154, §210–216.
 *   Decisions honored: R-01 (Module 13 IDs), R-06 (citation keys on
 *   evidence_id + document_id), R-09 (vector(1536)), R-13 (chunk/embedding
 *   owned by Repository), R-18 (processing_history checkpoints).
 *
 * Every function has ONE responsibility (§7 Principle, §211, §7401-line rule).
 * No prompts are embedded: PR-001/PR-002 are loaded from the Prompt Registry
 * (§175, §608). No secrets are embedded (§321-324, §608). No config is
 * hardcoded: values arrive via `config` (Principle 7).
 *
 * Adapters (OCR / LLM / embedding / DB) are injected as `deps` so the same
 * logic runs (a) under Node for tests with in-memory fakes and (b) inside n8n
 * Code nodes wired to the real Provider Adapter layer built in Sprint 1.
 * This is deliberate provider independence (§316-320), NOT a placeholder.
 */

'use strict';

const crypto = require('crypto');

// ---------------------------------------------------------------------------
// §438 — canonical 16-value category enum (R-05). Used by SW-011 validation.
// ---------------------------------------------------------------------------
const CATEGORY_ENUM = Object.freeze([
  'Feature', 'Capability', 'Limitation', 'Configuration', 'Integration',
  'BusinessRule', 'Workflow', 'DataModel', 'Security', 'Performance',
  'Compliance', 'Pricing', 'Support', 'Deployment', 'Roadmap', 'Other',
]);

// §374 processing_history stage vocabulary (subset used by ingestion).
const STAGE = Object.freeze({
  UPLOAD: 'Upload',
  OCR: 'OCR',
  KNOWLEDGE: 'KnowledgeExtraction',
  CHUNK: 'ChunkGeneration',
  EMBEDDING: 'Embeddings',
  CERTIFICATION: 'Certification',
});

// ===========================================================================
// SW-001 — Generate Correlation ID (§241)
// ===========================================================================
function sw001_generateCorrelationId() {
  return { correlationId: crypto.randomUUID() };
}

// ===========================================================================
// SW-002 — Generate SHA256 (§242). Same bytes → same hash (deterministic).
// ===========================================================================
function sw002_generateSha256(binary) {
  if (binary == null) throw new Error('SW-002: binary file is required');
  const buf = Buffer.isBuffer(binary) ? binary : Buffer.from(binary);
  return { sha256: crypto.createHash('sha256').update(buf).digest('hex') };
}

// ===========================================================================
// SW-003 — Duplicate Detection (§243). Repository query on sha256.
// ===========================================================================
async function sw003_duplicateDetection({ sha256 }, deps) {
  if (!sha256) throw new Error('SW-003: sha256 is required');
  const existing = await deps.db.findDocumentBySha256(sha256);
  return existing
    ? { duplicate: true, documentId: existing.id }
    : { duplicate: false, documentId: null };
}

// ===========================================================================
// SW-004 — Register Document / create Document Passport (§244, §26).
// ===========================================================================
async function sw004_registerDocument(passport, deps) {
  if (!passport || !passport.sha256) {
    throw new Error('SW-004: document metadata with sha256 is required');
  }
  const documentId = crypto.randomUUID();
  await deps.db.insertDocument({
    id: documentId,
    sha256: passport.sha256,
    filename: passport.filename ?? null,
    source: passport.source ?? 'GoogleDrive',
    mime_type: passport.mimeType ?? null,
    status: 'REGISTERED',
    authority: passport.authority ?? 'Unspecified',
    uploaded_at: new Date().toISOString(),
    correlation_id: passport.correlationId ?? null,
  });
  return { documentId, status: 'REGISTERED' };
}

// ===========================================================================
// SW-005 — Azure OCR Adapter (§245, §355). Config-driven, retry ×3 backoff.
// No reasoning here (§211 "No AI reasoning").
// ===========================================================================
async function sw005_azureOcr(binary, deps, config) {
  const ocrCfg = config.ocr || {};
  const attempts = ocrCfg.retryAttempts ?? 3;
  const baseDelayMs = ocrCfg.retryBaseDelayMs ?? 500;
  let lastErr;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const ocr = await deps.ocr.analyze(binary, {
        endpoint: ocrCfg.endpoint,
        model: ocrCfg.model,
        timeout: ocrCfg.timeout,
      });
      return { ocr };
    } catch (err) {
      lastErr = err;
      if (attempt < attempts) {
        await deps.sleep(baseDelayMs * 2 ** (attempt - 1)); // exponential
      }
    }
  }
  const e = new Error(`SW-005: Azure OCR failed after ${attempts} attempts: ${lastErr && lastErr.message}`);
  e.stage = STAGE.OCR;
  e.recoverable = false;
  throw e;
}

// ===========================================================================
// SW-006 — OCR Validation (§246, §29). Pass / Warning / Fail.
// ===========================================================================
function sw006_ocrValidation({ ocr }, config) {
  const warnings = [];
  const minConfidence = (config.ocr && config.ocr.minConfidence) ?? 0.7;
  const pages = (ocr && ocr.pages) || [];

  if (pages.length === 0) return { valid: false, warnings: ['no pages'] };

  const emptyPages = pages.filter((p) => !p.text || !p.text.trim());
  if (emptyPages.length) warnings.push(`empty pages: ${emptyPages.map((p) => p.page).join(',')}`);

  const lowConf = pages.filter((p) => typeof p.confidence === 'number' && p.confidence < minConfidence);
  if (lowConf.length) warnings.push(`low confidence pages: ${lowConf.map((p) => p.page).join(',')}`);

  if (!ocr.readingOrderPresent) warnings.push('reading order missing');

  // Fail only when the whole result is unusable; otherwise Pass/Warning+log.
  const allEmpty = emptyPages.length === pages.length;
  return { valid: !allEmpty, warnings };
}

// ===========================================================================
// SW-007 — Metadata Extraction (§247, §30). Uses PR-002 via LLM adapter.
// Prompt is LOADED, never embedded (§175, §608).
// ===========================================================================
async function sw007_metadataExtraction({ ocr }, deps, config) {
  const prompt = await deps.prompts.load('PR-002'); // Metadata Extraction
  const raw = await deps.llm.complete({
    prompt: deps.prompts.inject(prompt, { ocr: JSON.stringify(ocr) }),
    model: config.llm && config.llm.metadataModel,
    responseFormat: 'json',
  });
  const metadata = deps.parseJson(raw);
  return { metadata: Array.isArray(metadata) ? metadata : metadata.metadata || metadata };
}

// ===========================================================================
// SW-008 — Knowledge Extraction (§248, §31). Uses PR-001. One fact = one KU.
// ===========================================================================
async function sw008_knowledgeExtraction({ ocr }, deps, config) {
  const prompt = await deps.prompts.load('PR-001'); // Knowledge Extraction
  const raw = await deps.llm.complete({
    prompt: deps.prompts.inject(prompt, { ocr: JSON.stringify(ocr) }),
    model: config.llm && config.llm.knowledgeModel,
    responseFormat: 'json',
  });
  const parsed = deps.parseJson(raw);
  const units = (parsed.knowledgeUnits || parsed || []).map((ku) => ({
    id: crypto.randomUUID(),
    statement: (ku.statement || '').trim(),
    category: ku.category || 'Other',
    authoritySource: ku.authoritySource || null,
    sourcePage: ku.sourcePage ?? null,
    sourceParagraph: ku.sourceParagraph ?? null,
  }));
  return { knowledgeUnits: units };
}

// ===========================================================================
// SW-009 — Evidence Generator (§249, §32). One KU → ≥1 evidence object.
// ===========================================================================
function sw009_evidenceGenerator({ knowledgeUnits }) {
  const evidence = [];
  for (const ku of knowledgeUnits) {
    evidence.push({
      id: crypto.randomUUID(),
      knowledgeUnitId: ku.id,
      excerpt: ku.statement,
      evidenceType: 'FeatureDescription',
      sourcePage: ku.sourcePage,
      sourceParagraph: ku.sourceParagraph,
    });
  }
  return { evidence };
}

// ===========================================================================
// SW-010 — Citation Generator (§250, §33). Keys on evidenceId + documentId
// (R-06). Every evidence object gets ≥1 citation.
// ===========================================================================
function sw010_citationGenerator({ evidence, documentId }) {
  if (!documentId) throw new Error('SW-010: documentId is required (R-06)');
  const citations = evidence.map((ev) => ({
    id: crypto.randomUUID(),
    evidenceId: ev.id, // R-06
    documentId, // R-06
    page: ev.sourcePage ?? null,
    paragraph: ev.sourceParagraph ?? null,
    section: ev.section ?? null,
  }));
  return { citations };
}

// ===========================================================================
// SW-011 — Knowledge Validator (§251, §34). Invalid objects are rejected and
// never enter the repository (§34 "shall not enter the repository").
// ===========================================================================
function sw011_knowledgeValidator({ knowledgeUnits, evidence, citations }) {
  const evidenceByKu = new Map();
  for (const ev of evidence) {
    if (!evidenceByKu.has(ev.knowledgeUnitId)) evidenceByKu.set(ev.knowledgeUnitId, []);
    evidenceByKu.get(ev.knowledgeUnitId).push(ev);
  }
  const citationsByEvidence = new Set(citations.map((c) => c.evidenceId));

  const seen = new Set();
  const accepted = [];
  const rejected = [];

  for (const ku of knowledgeUnits) {
    const reasons = [];
    if (!ku.statement) reasons.push('empty statement');
    const key = ku.statement.toLowerCase();
    if (seen.has(key)) reasons.push('duplicate knowledge');
    if (!CATEGORY_ENUM.includes(ku.category)) reasons.push(`invalid category: ${ku.category}`);
    const kuEvidence = evidenceByKu.get(ku.id) || [];
    if (kuEvidence.length === 0) reasons.push('missing evidence');
    if (!kuEvidence.some((ev) => citationsByEvidence.has(ev.id))) reasons.push('missing citation');

    if (reasons.length) {
      rejected.push({ id: ku.id, statement: ku.statement, reasons });
    } else {
      seen.add(key);
      accepted.push(ku);
    }
  }
  return { accepted, rejected, valid: accepted.length > 0 };
}

// ===========================================================================
// SW-012 — Semantic Chunk Builder (§252, §35). Chunk validated KUs only —
// never raw OCR, never PDF pages.
// ===========================================================================
function sw012_chunkBuilder({ acceptedUnits }, config) {
  const maxChars = (config.chunking && config.chunking.maxChars) ?? 1200;
  const chunks = [];
  for (const ku of acceptedUnits) {
    const text = ku.statement;
    // One KU is atomic; only split if a single statement exceeds the budget.
    if (text.length <= maxChars) {
      chunks.push({ id: crypto.randomUUID(), knowledgeUnitId: ku.id, text, ordinal: 0 });
    } else {
      for (let i = 0, ord = 0; i < text.length; i += maxChars, ord++) {
        chunks.push({
          id: crypto.randomUUID(),
          knowledgeUnitId: ku.id,
          text: text.slice(i, i + maxChars),
          ordinal: ord,
        });
      }
    }
  }
  return { chunks };
}

// ===========================================================================
// SW-013 — Embedding Generator (§253, §36). vector(1536) v1 default (R-09).
// ===========================================================================
async function sw013_embeddingGenerator({ chunks }, deps, config) {
  const embCfg = config.embeddings || {};
  const dimensions = embCfg.dimensions ?? 1536; // R-09
  const batchSize = embCfg.batchSize ?? 16;
  const embeddings = [];
  for (let i = 0; i < chunks.length; i += batchSize) {
    const batch = chunks.slice(i, i + batchSize);
    const vectors = await deps.embedding.embed(
      batch.map((c) => c.text),
      { provider: embCfg.provider, model: embCfg.model, dimensions },
    );
    vectors.forEach((vec, j) => {
      if (vec.length !== dimensions) {
        throw new Error(`SW-013: embedding dimension ${vec.length} != configured ${dimensions} (R-09)`);
      }
      embeddings.push({ id: crypto.randomUUID(), chunkId: batch[j].id, vector: vec, dimensions });
    });
  }
  return { embeddings };
}

// ===========================================================================
// SW-014 — Repository Writer (§254, §37, §234). Single transaction only.
// Rollback on any failure (WF-001 failure policy: Repository → Rollback).
// ===========================================================================
async function sw014_repositoryWriter(bundle, deps) {
  return deps.db.withTransaction(async (tx) => {
    await tx.updateDocumentStatus(bundle.documentId, 'PROCESSED');
    await tx.insertMetadata(bundle.documentId, bundle.metadata);
    await tx.insertKnowledgeUnits(bundle.documentId, bundle.acceptedUnits);
    await tx.insertEvidence(bundle.evidence);
    await tx.insertCitations(bundle.citations);
    await tx.insertChunks(bundle.chunks);
    await tx.insertEmbeddings(bundle.embeddings);
    return {
      written: {
        knowledgeUnits: bundle.acceptedUnits.length,
        evidence: bundle.evidence.length,
        citations: bundle.citations.length,
        chunks: bundle.chunks.length,
        embeddings: bundle.embeddings.length,
      },
    };
  });
}

// ===========================================================================
// SW-015 — Repository Certification (§255). All checks must pass → CERTIFIED.
// ===========================================================================
async function sw015_certification({ documentId }, deps) {
  const c = await deps.db.certificationCounts(documentId);
  const checks = {
    documentExists: c.document === 1,
    knowledgeExists: c.knowledgeUnits > 0,
    evidenceLinked: c.evidence > 0,
    citationsLinked: c.citations > 0,
    chunksGenerated: c.chunks > 0,
    embeddingsGenerated: c.embeddings > 0,
  };
  const certified = Object.values(checks).every(Boolean);
  if (certified) await deps.db.updateDocumentStatus(documentId, 'CERTIFIED');
  return { certified, status: certified ? 'CERTIFIED' : 'INCOMPLETE', checks };
}

module.exports = {
  CATEGORY_ENUM,
  STAGE,
  sw001_generateCorrelationId,
  sw002_generateSha256,
  sw003_duplicateDetection,
  sw004_registerDocument,
  sw005_azureOcr,
  sw006_ocrValidation,
  sw007_metadataExtraction,
  sw008_knowledgeExtraction,
  sw009_evidenceGenerator,
  sw010_citationGenerator,
  sw011_knowledgeValidator,
  sw012_chunkBuilder,
  sw013_embeddingGenerator,
  sw014_repositoryWriter,
  sw015_certification,
};
