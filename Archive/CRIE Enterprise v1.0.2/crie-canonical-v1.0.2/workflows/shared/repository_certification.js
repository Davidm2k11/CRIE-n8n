/**
 * CRIE — Repository Certification Framework + Quality Score + Versioning
 * Sprint 4 · Repository · targets v0.5.0
 *
 * Source of truth: CRIE Enterprise Specification v1.1 (frozen).
 *   §55 / §428 / §512 / §527 certification; §511 quality score;
 *   §53 / §519 versioning + lineage; §518 knowledge lifecycle states;
 *   §524/§525 integrity + governance gates; §426 lifecycle rules.
 *   Decisions: R-05 (16-value category enum), R-06 (citation keys),
 *   R-13 (chunk/embedding owned by Repository).
 *
 * Depends on Sprint 2 migration 0018 columns (quality_score, lifecycle_state,
 * previous_version, created_by, change_reason) and Sprint 3 ingestion output.
 * Does NOT re-implement ingestion (Sprint 3) or retrieval (Sprint 5).
 */

'use strict';

// §438 canonical 16-value category enum (R-05) — shared contract with Sprint 3.
const CATEGORY_ENUM = Object.freeze([
  'Feature', 'Capability', 'Limitation', 'Configuration', 'Integration',
  'BusinessRule', 'Workflow', 'DataModel', 'Security', 'Performance',
  'Compliance', 'Pricing', 'Support', 'Deployment', 'Roadmap', 'Other',
]);

// §518 Knowledge Unit lifecycle states.
const LIFECYCLE = Object.freeze({
  DRAFT: 'Draft', VALIDATED: 'Validated', CERTIFIED: 'Certified',
  DEPRECATED: 'Deprecated', ARCHIVED: 'Archived',
});

// ===========================================================================
// §511 — Knowledge Quality Score (0.00 → 1.00)
// Deterministic, platform-computed (Principle: deterministic before AI).
// Factors: OCR confidence, citation completeness, structural quality,
// statement clarity, category confidence, duplicate probability.
// ===========================================================================
function computeQualityScore(ku, ctx, config) {
  const w = (config.repository && config.repository.qualityWeights) || {
    ocrConfidence: 0.25, citationCompleteness: 0.2, structuralQuality: 0.15,
    statementClarity: 0.15, categoryConfidence: 0.15, duplicateProbability: 0.1,
  };
  const clamp = (x) => Math.max(0, Math.min(1, x));

  const ocrConfidence = clamp(ctx.ocrConfidence ?? 1);
  const citationCompleteness = ctx.citationCount > 0 ? 1 : 0;
  const structuralQuality = ku.sourcePage != null && ku.sourceParagraph != null ? 1 : 0.5;
  const len = (ku.statement || '').trim().length;
  const statementClarity = clamp(len === 0 ? 0 : len < 12 ? 0.4 : len > 400 ? 0.6 : 1);
  const categoryConfidence = CATEGORY_ENUM.includes(ku.category) ? 1 : 0;
  const duplicateProbability = clamp(ctx.duplicateProbability ?? 0);

  const score =
    w.ocrConfidence * ocrConfidence +
    w.citationCompleteness * citationCompleteness +
    w.structuralQuality * structuralQuality +
    w.statementClarity * statementClarity +
    w.categoryConfidence * categoryConfidence +
    w.duplicateProbability * (1 - duplicateProbability);

  const total = Object.values(w).reduce((a, b) => a + b, 0);
  return Math.round((score / total) * 100) / 100;
}

// ===========================================================================
// §512 — Per-Knowledge-Unit certification checklist (pre-insertion gate).
// A KU is certifiable only if every check passes; else it needs review.
// ===========================================================================
function certifyKnowledgeUnit(ku, ctx, config) {
  const threshold = (config.repository && config.repository.qualityThreshold) ?? 0.6;
  const quality = computeQualityScore(ku, ctx, config);
  const checks = {
    atomicStatement: !!(ku.statement && ku.statement.trim()),
    validCategory: CATEGORY_ENUM.includes(ku.category),          // R-05
    authorityAssigned: !!ku.authoritySource,
    evidenceExists: ctx.evidenceCount > 0,
    citationExists: ctx.citationCount > 0,                        // R-06
    duplicateCheckPassed: !ctx.isDuplicate,
    qualityAboveThreshold: quality >= threshold,
  };
  const certified = Object.values(checks).every(Boolean);
  return {
    knowledgeUnitId: ku.id,
    certified,
    qualityScore: quality,
    lifecycleState: certified ? LIFECYCLE.CERTIFIED : LIFECYCLE.DRAFT,
    checks,
    reviewRequired: !certified, // §513 uncertain knowledge is not auto-certified
  };
}

// ===========================================================================
// §428 / §527 — Document-level Repository Certification.
// Verifies structure, quality, evidence, citations, embeddings, version
// integrity, and transaction success. Emits §527 certification object.
// ===========================================================================
function certifyDocument({ documentId, repositoryVersion, unitResults, counts, transactionCommitted }) {
  const certifiedUnits = unitResults.filter((r) => r.certified);
  const checks = {
    repositoryStructure: counts.document === 1,
    knowledgeQuality: certifiedUnits.length > 0,
    evidenceQuality: counts.evidence > 0,
    citationCompleteness: counts.citations > 0,
    embeddingAvailability: counts.embeddings > 0,
    versionIntegrity: !!repositoryVersion,
    transactionSuccess: transactionCommitted === true,
  };
  const certified = Object.values(checks).every(Boolean);
  const qualityScore = certifiedUnits.length
    ? Math.round((certifiedUnits.reduce((a, r) => a + r.qualityScore, 0) / certifiedUnits.length) * 100) / 100
    : 0;
  return {
    repositoryVersion: repositoryVersion || '',
    certified,
    certificationDate: new Date().toISOString(),
    qualityScore,
    checks,
    certifiedUnits: certifiedUnits.length,
    totalUnits: unitResults.length,
  };
}

// ===========================================================================
// §519 / §53 — Versioning + lineage helpers.
// New version of a KU links to its predecessor via previous_version and
// records createdBy + changeReason. Old versions are preserved (§522: deleted
// KUs become Deprecated, never physically removed).
// ===========================================================================
function buildVersionedUnit(newUnit, previousUnit, { createdBy, changeReason }) {
  return {
    ...newUnit,
    previous_version: previousUnit ? previousUnit.id : null, // §519 lineage
    created_by: createdBy || 'ingestion',
    change_reason: changeReason || (previousUnit ? 'update' : 'initial'),
    lifecycle_state: LIFECYCLE.CERTIFIED,
  };
}

function deprecateUnit(unit, { changeReason }) {
  return { ...unit, lifecycle_state: LIFECYCLE.DEPRECATED, change_reason: changeReason || 'superseded' };
}

module.exports = {
  CATEGORY_ENUM,
  LIFECYCLE,
  computeQualityScore,
  certifyKnowledgeUnit,
  certifyDocument,
  buildVersionedUnit,
  deprecateUnit,
};
