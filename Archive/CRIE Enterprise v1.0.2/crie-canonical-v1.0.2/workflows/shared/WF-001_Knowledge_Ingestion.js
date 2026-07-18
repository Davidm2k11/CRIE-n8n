/**
 * CRIE — WF-001 Knowledge Ingestion (Master Workflow)
 * Sprint 3 · targets v0.4.0
 *
 * Source of truth: v1.1 §154 (execution + failure policy), §210–216 (node
 * list, common pattern Initialize→Validate→Execute→Verify→Persist→Log→Return,
 * standard retry policy, execution summary §216).
 *
 * Deterministic-before-AI (Principle 2): correlation → hash → dup → register →
 * OCR → validate run before any LLM node. Failure policy (§154):
 *   Duplicate  → Stop
 *   OCR        → Retry ×3 (inside SW-005), then human review
 *   Extraction → Human Review
 *   Repository → Rollback (single transaction in SW-014)
 *
 * A processing_history checkpoint is written at each stage (R-18, §424, §372):
 * PENDING before the stage, COMPLETED/FAILED after.
 */

'use strict';

const sw = require('../shared/module13_ingestion');
const { STAGE } = sw;

/** Write a processing_history checkpoint (R-18). Append-only. */
async function checkpoint(deps, { documentId, stage, status, correlationId }) {
  if (!documentId) return; // pre-registration stages have no document yet
  await deps.db.appendProcessingHistory({
    document_id: documentId,
    stage,
    status,
    correlation_id: correlationId,
  });
}

/**
 * Run WF-001 for one document.
 * @param {{ binary: Buffer, filename?: string, mimeType?: string,
 *           source?: string, authority?: string }} input
 * @param {object} deps  injected adapters (db, ocr, llm, embedding, prompts,
 *                       logger, telemetry, sleep, parseJson)
 * @param {object} config runtime configuration (from registry, R-08)
 */
async function runWF001(input, deps, config) {
  const startedAt = Date.now();
  const { correlationId } = sw.sw001_generateCorrelationId();
  const logger = deps.logger.child({ workflow: 'WF-001', correlationId });
  let documentId = null;
  let outcome = 'SUCCESS';

  const summary = {
    workflow: 'WF-001',
    executionId: correlationId,
    status: '',
    duration: '',
    documentsProcessed: 0,
    knowledgeUnits: 0,
    evidenceObjects: 0,
    chunks: 0,
    embeddings: 0,
    cost: 0,
  };

  try {
    // --- Initialize / Validate ---------------------------------------------
    if (!input || input.binary == null) throw new Error('WF-001: input.binary is required');

    // --- SHA256 -------------------------------------------------------------
    const { sha256 } = sw.sw002_generateSha256(input.binary);

    // --- Duplicate Detection → Stop ----------------------------------------
    const dup = await sw.sw003_duplicateDetection({ sha256 }, deps);
    if (dup.duplicate) {
      logger.info('duplicate document — stopping', { documentId: dup.documentId });
      summary.status = 'DUPLICATE';
      summary.duration = `${Date.now() - startedAt}ms`;
      await deps.telemetry.record(summary);
      return { status: 'DUPLICATE', documentId: dup.documentId, summary };
    }

    // --- Register Document (Upload checkpoint) ------------------------------
    const reg = await sw.sw004_registerDocument(
      { sha256, filename: input.filename, mimeType: input.mimeType, source: input.source, authority: input.authority, correlationId },
      deps,
    );
    documentId = reg.documentId;
    summary.documentsProcessed = 1;
    await checkpoint(deps, { documentId, stage: STAGE.UPLOAD, status: 'COMPLETED', correlationId });

    // --- OCR (retry ×3 in adapter) -----------------------------------------
    await checkpoint(deps, { documentId, stage: STAGE.OCR, status: 'PENDING', correlationId });
    let ocrOut;
    try {
      ocrOut = await sw.sw005_azureOcr(input.binary, deps, config);
    } catch (err) {
      await checkpoint(deps, { documentId, stage: STAGE.OCR, status: 'FAILED', correlationId });
      await deps.db.updateDocumentStatus(documentId, 'HUMAN_REVIEW'); // §29 fail-again → human review
      throw err;
    }
    const ocrCheck = sw.sw006_ocrValidation(ocrOut, config);
    if (!ocrCheck.valid) {
      await checkpoint(deps, { documentId, stage: STAGE.OCR, status: 'FAILED', correlationId });
      await deps.db.updateDocumentStatus(documentId, 'HUMAN_REVIEW');
      throw Object.assign(new Error('WF-001: OCR validation failed'), { stage: STAGE.OCR });
    }
    if (ocrCheck.warnings.length) logger.warn('OCR warnings', { warnings: ocrCheck.warnings });
    await checkpoint(deps, { documentId, stage: STAGE.OCR, status: 'COMPLETED', correlationId });

    // --- Knowledge / Metadata / Evidence / Citation / Validate -------------
    await checkpoint(deps, { documentId, stage: STAGE.KNOWLEDGE, status: 'PENDING', correlationId });
    let metaOut, kuOut;
    try {
      metaOut = await sw.sw007_metadataExtraction(ocrOut, deps, config);
      kuOut = await sw.sw008_knowledgeExtraction(ocrOut, deps, config);
    } catch (err) {
      await checkpoint(deps, { documentId, stage: STAGE.KNOWLEDGE, status: 'FAILED', correlationId });
      await deps.db.updateDocumentStatus(documentId, 'HUMAN_REVIEW'); // Extraction → Human Review
      throw err;
    }

    const evOut = sw.sw009_evidenceGenerator(kuOut);
    const citeOut = sw.sw010_citationGenerator({ evidence: evOut.evidence, documentId }); // R-06
    const validation = sw.sw011_knowledgeValidator({
      knowledgeUnits: kuOut.knowledgeUnits,
      evidence: evOut.evidence,
      citations: citeOut.citations,
    });
    if (validation.rejected.length) logger.warn('rejected knowledge units', { rejected: validation.rejected });
    if (!validation.valid) {
      await checkpoint(deps, { documentId, stage: STAGE.KNOWLEDGE, status: 'FAILED', correlationId });
      await deps.db.updateDocumentStatus(documentId, 'HUMAN_REVIEW');
      throw Object.assign(new Error('WF-001: no valid knowledge units extracted'), { stage: STAGE.KNOWLEDGE });
    }
    // Keep only evidence/citations attached to accepted KUs (rejected never enter repo, §34).
    const acceptedIds = new Set(validation.accepted.map((k) => k.id));
    const evidence = evOut.evidence.filter((e) => acceptedIds.has(e.knowledgeUnitId));
    const acceptedEvidenceIds = new Set(evidence.map((e) => e.id));
    const citations = citeOut.citations.filter((c) => acceptedEvidenceIds.has(c.evidenceId));
    await checkpoint(deps, { documentId, stage: STAGE.KNOWLEDGE, status: 'COMPLETED', correlationId });

    // --- Chunk (validated KUs only) ----------------------------------------
    await checkpoint(deps, { documentId, stage: STAGE.CHUNK, status: 'PENDING', correlationId });
    const chunkOut = sw.sw012_chunkBuilder({ acceptedUnits: validation.accepted }, config);
    await checkpoint(deps, { documentId, stage: STAGE.CHUNK, status: 'COMPLETED', correlationId });

    // --- Embeddings (1536, R-09) -------------------------------------------
    await checkpoint(deps, { documentId, stage: STAGE.EMBEDDING, status: 'PENDING', correlationId });
    const embOut = await sw.sw013_embeddingGenerator(chunkOut, deps, config);
    await checkpoint(deps, { documentId, stage: STAGE.EMBEDDING, status: 'COMPLETED', correlationId });

    // --- Repository Writer (single transaction; rollback on failure) -------
    try {
      await sw.sw014_repositoryWriter(
        {
          documentId,
          metadata: metaOut.metadata,
          acceptedUnits: validation.accepted,
          evidence,
          citations,
          chunks: chunkOut.chunks,
          embeddings: embOut.embeddings,
        },
        deps,
      );
    } catch (err) {
      logger.error('repository write failed — rolled back', { error: err.message });
      throw Object.assign(err, { stage: 'Repository' }); // WF failure policy: Repository → Rollback
    }

    // --- Certification -----------------------------------------------------
    await checkpoint(deps, { documentId, stage: STAGE.CERTIFICATION, status: 'PENDING', correlationId });
    const cert = await sw.sw015_certification({ documentId }, deps);
    await checkpoint(deps, {
      documentId, stage: STAGE.CERTIFICATION,
      status: cert.certified ? 'COMPLETED' : 'FAILED', correlationId,
    });
    if (!cert.certified) {
      throw Object.assign(new Error('WF-001: certification failed'), { checks: cert.checks });
    }

    // --- Summary / Log / Return --------------------------------------------
    summary.status = 'CERTIFIED';
    summary.knowledgeUnits = validation.accepted.length;
    summary.evidenceObjects = evidence.length;
    summary.chunks = chunkOut.chunks.length;
    summary.embeddings = embOut.embeddings.length;
    summary.cost = (deps.telemetry.accumulatedCost && deps.telemetry.accumulatedCost()) || 0;
    summary.duration = `${Date.now() - startedAt}ms`;
    await deps.telemetry.record(summary);
    logger.info('ingestion certified', { documentId });
    return { status: 'CERTIFIED', documentId, certification: cert, summary };
  } catch (err) {
    outcome = 'FAILED';
    summary.status = 'FAILED';
    summary.duration = `${Date.now() - startedAt}ms`;
    await deps.telemetry.record(summary).catch(() => {});
    deps.logger.error('WF-001 failed', { correlationId, documentId, stage: err.stage, error: err.message });
    return { status: 'FAILED', documentId, error: err.message, stage: err.stage || null, summary };
  } finally {
    void outcome;
  }
}

module.exports = { runWF001, checkpoint };
