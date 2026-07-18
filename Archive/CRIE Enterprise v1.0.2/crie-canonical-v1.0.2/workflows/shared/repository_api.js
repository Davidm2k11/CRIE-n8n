/**
 * CRIE — Repository API (Module 36, §365 / §56)
 * Sprint 4 · Repository · targets v0.5.0
 *
 * Provides controlled repository access. Minimum operations (§365 + §56):
 *   CreateDocument, UpdateDocument, ArchiveDocument, GetKnowledgeUnit,
 *   SearchMetadata/SearchKnowledge, RebuildEmbeddings, RepositoryStatistics,
 *   RepositoryHealth.
 *
 * Responses follow canonical contracts (§226 "Responses SHALL follow canonical
 * contracts"). The Repository is never bypassed (§608): all persistence goes
 * through the hardened transactional writer.
 *
 * Certified-only retrieval boundary (§518): SearchKnowledge/GetKnowledgeUnit
 * only surface CERTIFIED knowledge units.
 *
 * Deliberately NOT built here (future sprints): the actual retrieval pipeline
 * (Sprint 5), reasoning (Sprint 6), dashboards/BI (Sprint 8). RebuildEmbeddings
 * enqueues/limits per §523 policy but the embedding generation itself reuses
 * Sprint 3 SW-013 via the injected embedding adapter — no new capability.
 */

'use strict';

const cert = require('./repository_certification');
const writer = require('./repository_writer');
const hs = require('./repository_health_statistics');

function createRepositoryApi(deps, config) {
  const ok = (data) => ({ status: 'OK', data });
  const fail = (code, message, extra = {}) => ({ status: 'ERROR', error: { code, message, ...extra } });

  return {
    // --- CreateDocument: full certified write of an ingested bundle ---------
    // Runs per-KU certification (§512), builds version lineage (§519),
    // writes in one transaction (§148), then document certification (§428/§527).
    async createDocument(bundle) {
      try {
        // §512 per-unit certification + §511 quality score.
        const unitResults = [];
        const certifiedUnits = [];
        for (const ku of bundle.knowledgeUnits || []) {
          const ctx = {
            ocrConfidence: bundle.ocrConfidence,
            evidenceCount: (bundle.evidence || []).filter((e) => e.knowledgeUnitId === ku.id).length,
            citationCount: (bundle.citations || []).filter((c) =>
              (bundle.evidence || []).some((e) => e.id === c.evidenceId && e.knowledgeUnitId === ku.id)).length,
            isDuplicate: !!ku.isDuplicate,
            duplicateProbability: ku.duplicateProbability,
          };
          const r = cert.certifyKnowledgeUnit(ku, ctx, config);
          unitResults.push(r);
          if (r.certified) {
            const prev = bundle.previousVersions && bundle.previousVersions[ku.id];
            certifiedUnits.push({
              ...cert.buildVersionedUnit(ku, prev, {
                createdBy: bundle.createdBy, changeReason: bundle.changeReason,
              }),
              quality_score: r.qualityScore,
            });
          }
        }
        if (certifiedUnits.length === 0) {
          return fail('NO_CERTIFIABLE_KNOWLEDGE', 'No knowledge units passed certification (§512)', {
            unitResults,
          });
        }

        // Keep only evidence/citations attached to certified units (§34/§427).
        const certIds = new Set(certifiedUnits.map((k) => k.id));
        const evidence = (bundle.evidence || []).filter((e) => certIds.has(e.knowledgeUnitId));
        const evIds = new Set(evidence.map((e) => e.id));
        const citations = (bundle.citations || []).filter((c) => evIds.has(c.evidenceId));
        const chunks = (bundle.chunks || []).filter((ch) => certIds.has(ch.knowledgeUnitId));
        const chunkIds = new Set(chunks.map((c) => c.id));
        const embeddings = (bundle.embeddings || []).filter((em) => chunkIds.has(em.chunkId));

        // §423/§519 new repository version for this write.
        const repositoryVersion = await deps.db.nextRepositoryVersion(bundle.changeReason || 'ingestion');

        // §148 single transaction (integrity/governance gates run inside writer).
        const writeResult = await writer.writeRepository(
          { documentId: bundle.documentId, metadata: bundle.metadata, knowledgeUnits: certifiedUnits,
            evidence, citations, chunks, embeddings },
          deps,
        );

        // §428/§527 document certification.
        const counts = await deps.db.certificationCounts(bundle.documentId);
        const certification = cert.certifyDocument({
          documentId: bundle.documentId,
          repositoryVersion,
          unitResults,
          counts,
          transactionCommitted: writeResult.committed,
        });
        if (certification.certified) {
          await deps.db.updateDocumentStatus(bundle.documentId, 'CERTIFIED');
        }
        return ok({ documentId: bundle.documentId, repositoryVersion, certification, written: writeResult.written });
      } catch (err) {
        return fail('WRITE_FAILED', err.message, { violations: err.violations, stage: err.stage });
      }
    },

    // --- UpdateDocument: version lineage + deprecate superseded units (§519/§522)
    async updateDocument(documentId, changes) {
      try {
        if (!documentId) return fail('BAD_REQUEST', 'documentId required');
        await deps.db.updateDocument(documentId, changes);
        return ok({ documentId, updated: Object.keys(changes || {}) });
      } catch (err) {
        return fail('UPDATE_FAILED', err.message);
      }
    },

    // --- ArchiveDocument (§531): never physically deletes certified knowledge (§530)
    async archiveDocument(documentId) {
      try {
        await deps.db.updateDocumentStatus(documentId, 'ARCHIVED');
        await deps.db.appendProcessingHistory({ document_id: documentId, stage: 'Archive', status: 'COMPLETED' });
        return ok({ documentId, status: 'ARCHIVED', recoverable: true });
      } catch (err) {
        return fail('ARCHIVE_FAILED', err.message);
      }
    },

    // --- GetKnowledgeUnit: certified-only (§518) ---------------------------
    async getKnowledgeUnit(id) {
      const ku = await deps.db.getKnowledgeUnit(id);
      if (!ku) return fail('NOT_FOUND', `knowledge unit ${id} not found`);
      if (ku.lifecycle_state !== cert.LIFECYCLE.CERTIFIED) {
        return fail('NOT_CERTIFIED', `knowledge unit ${id} is ${ku.lifecycle_state}, not Certified (§518)`);
      }
      return ok(ku);
    },

    // --- SearchMetadata (§56) ---------------------------------------------
    async searchMetadata(query) {
      const rows = await deps.db.searchMetadata(query || {});
      return ok(rows);
    },

    // --- SearchKnowledge (§365): certified-only metadata-level search -------
    async searchKnowledge(query) {
      const rows = await deps.db.searchKnowledge({ ...query, lifecycle_state: cert.LIFECYCLE.CERTIFIED });
      return ok(rows);
    },

    // --- RebuildEmbeddings (§523): reserved triggers only ------------------
    async rebuildEmbeddings(scope) {
      const reason = (scope && scope.reason) || null;
      const allowed = ['EmbeddingModelChange', 'ChunkingStrategyChange', 'AdministrativeRequest'];
      if (!allowed.includes(reason)) {
        return fail('NOT_ALLOWED', `repository-wide embedding rebuild reserved for ${allowed.join('/')} (§523)`);
      }
      const chunks = await deps.db.listChunks(scope);
      let regenerated = 0;
      const batchSize = (config.embeddings && config.embeddings.batchSize) || 16;
      const dimensions = (config.embeddings && config.embeddings.dimensions) || 1536; // R-09
      for (let i = 0; i < chunks.length; i += batchSize) {
        const batch = chunks.slice(i, i + batchSize);
        const vecs = await deps.embedding.embed(batch.map((c) => c.text), {
          provider: config.embeddings && config.embeddings.provider,
          model: config.embeddings && config.embeddings.model,
          dimensions,
        });
        vecs.forEach((v, j) => {
          if (v.length !== dimensions) throw new Error(`embedding dimension ${v.length} != ${dimensions} (R-09)`);
          regenerated++;
          void batch[j];
        });
        await deps.db.replaceEmbeddings(batch.map((c, j) => ({ chunkId: c.id, vector: vecs[j], dimensions })));
      }
      return ok({ regenerated, reason });
    },

    // --- RepositoryStatistics (§529) --------------------------------------
    async repositoryStatistics() {
      const agg = await deps.db.repositoryAggregates();
      const health = hs.computeHealthScore(agg, config);
      return ok(hs.computeStatistics(agg, health));
    },

    // --- RepositoryHealth (§528 / §366) -----------------------------------
    async repositoryHealth() {
      const agg = await deps.db.repositoryAggregates();
      return ok(hs.computeHealthScore(agg, config));
    },
  };
}

module.exports = { createRepositoryApi };
