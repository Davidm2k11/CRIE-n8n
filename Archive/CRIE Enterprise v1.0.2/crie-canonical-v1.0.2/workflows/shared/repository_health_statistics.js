/**
 * CRIE — Repository Health Score (§528) + Repository Statistics (§529)
 * Sprint 4 · Repository · targets v0.5.0
 *
 * Source of truth: v1.1 §528 (health factors, 0→100), §529 (required stats),
 *   §533 (analytics inputs). Health/statistics are computed from repository
 *   aggregates supplied by the DB adapter; presentation as Supabase views +
 *   BI tool is Sprint 8 (R-17) and is NOT built here.
 */

'use strict';

// ===========================================================================
// §528 — Repository Health Score (0 → 100).
// Factors: certified knowledge %, duplicate rate, missing citations,
// broken relationships, embedding coverage, extraction success rate.
// ===========================================================================
function computeHealthScore(agg, config) {
  const w = (config.repository && config.repository.healthWeights) || {
    certifiedKnowledgePct: 0.25, duplicateRate: 0.15, missingCitations: 0.15,
    brokenRelationships: 0.15, embeddingCoverage: 0.15, extractionSuccessRate: 0.15,
  };
  const safe = (n, d) => (d > 0 ? n / d : 1); // empty repo is trivially healthy on ratio factors
  const clamp = (x) => Math.max(0, Math.min(1, x));

  const factors = {
    certifiedKnowledgePct: clamp(safe(agg.certifiedKnowledgeUnits, agg.knowledgeUnits)),
    duplicateRate: clamp(1 - safe(agg.duplicateKnowledgeUnits, agg.knowledgeUnits)),
    missingCitations: clamp(1 - safe(agg.evidenceWithoutCitations, agg.evidence)),
    brokenRelationships: clamp(1 - safe(agg.brokenRelationships, agg.relationships || 0)),
    embeddingCoverage: clamp(safe(agg.embeddings, agg.chunks)),
    extractionSuccessRate: clamp(safe(agg.certifiedDocuments, agg.documents)),
  };

  const total = Object.values(w).reduce((a, b) => a + b, 0);
  const weighted = Object.keys(w).reduce((sum, k) => sum + w[k] * factors[k], 0);
  const score = Math.round((weighted / total) * 100);

  let status = 'Critical';
  const t = (config.repository && config.repository.healthThresholds) || { healthy: 85, degraded: 60 };
  if (score >= t.healthy) status = 'Healthy';
  else if (score >= t.degraded) status = 'Degraded';

  return { score, status, factors };
}

// ===========================================================================
// §529 — Repository Statistics. Updates automatically (recomputed on demand).
// ===========================================================================
function computeStatistics(agg, health) {
  return {
    documents: agg.documents,
    knowledgeUnits: agg.knowledgeUnits,
    evidenceObjects: agg.evidence,
    citations: agg.citations,
    retrievalChunks: agg.chunks,
    embeddings: agg.embeddings,
    averageQuality: agg.averageQuality ?? 0,
    repositorySizeBytes: agg.repositorySizeBytes ?? 0,
    averageVersion: agg.averageVersion ?? 1,
    repositoryHealth: health ? health.score : null,
  };
}

module.exports = { computeHealthScore, computeStatistics };
