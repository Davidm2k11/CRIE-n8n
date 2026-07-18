/**
 * CRIE — Repository Writer (hardened) + Integrity/Governance Gates
 * Sprint 4 · Repository · targets v0.5.0
 *
 * Source of truth: v1.1 §148 (single transaction; partial writes prohibited),
 *   §234 (transaction policy), §524 (integrity engine), §525 (governance
 *   rules), §427 (integrity rules), §426 (lifecycle), §425 + R-13 (ownership).
 *
 * This HARDENS the Sprint 3 SW-014 writer: it runs the §524 integrity checks
 * and §525 governance checks BEFORE the transaction, writes all canonical
 * objects in ONE transaction, and rolls back on any failure. Chunks and
 * embeddings are written here because the Repository owns them (R-13, §425);
 * Retrieval only consumes them (enforced by assertRepositoryOwnership).
 */

'use strict';

const { CATEGORY_ENUM } = require('./repository_certification');

// §425 + R-13 — objects the Repository owns and therefore may persist.
const REPOSITORY_OWNED = Object.freeze([
  'document', 'metadata', 'knowledgeUnit', 'evidence', 'citation', 'chunk', 'embedding',
]);
// Objects the Repository must NEVER store (§427, §54).
const FORBIDDEN_IN_REPOSITORY = Object.freeze(['complianceResult', 'contextPackage', 'prompt', 'aiConversation']);

/** R-13 / §425 guard: refuse to persist anything the Repository does not own. */
function assertRepositoryOwnership(objectType) {
  if (FORBIDDEN_IN_REPOSITORY.includes(objectType)) {
    throw new Error(`Repository ownership violation: '${objectType}' SHALL NEVER be stored in the Repository (§427/§54)`);
  }
  if (!REPOSITORY_OWNED.includes(objectType)) {
    throw new Error(`Repository ownership violation: '${objectType}' is not a Repository-owned object (§425)`);
  }
  return true;
}

// ===========================================================================
// §524 Integrity Engine + §525 Governance Rules + §427 Integrity Rules.
// Runs before commit. Any violation blocks the write (and thus certification).
// ===========================================================================
function checkIntegrity(bundle) {
  const violations = [];
  const { knowledgeUnits = [], evidence = [], citations = [], chunks = [], embeddings = [] } = bundle;

  const kuIds = new Set(knowledgeUnits.map((k) => k.id));
  const evidenceByKu = new Map();
  for (const ev of evidence) {
    if (!kuIds.has(ev.knowledgeUnitId)) violations.push(`evidence ${ev.id} references missing knowledge unit`); // §427
    evidenceByKu.set(ev.knowledgeUnitId, (evidenceByKu.get(ev.knowledgeUnitId) || 0) + 1);
  }
  // §427: Knowledge Units without Evidence.
  for (const ku of knowledgeUnits) {
    if (!evidenceByKu.get(ku.id)) violations.push(`knowledge unit ${ku.id} has no evidence`);
    if (!ku.authoritySource) violations.push(`knowledge unit ${ku.id} has no authority (§525)`); // §525
    if (!CATEGORY_ENUM.includes(ku.category)) violations.push(`knowledge unit ${ku.id} invalid category (R-05)`);
  }
  // §427: Evidence without Citations.
  const evidenceIds = new Set(evidence.map((e) => e.id));
  const citedEvidence = new Set(citations.map((c) => c.evidenceId));
  for (const ev of evidence) {
    if (!citedEvidence.has(ev.id)) violations.push(`evidence ${ev.id} has no citation (§427)`);
  }
  // §427: Chunks without Knowledge Units; orphan chunks (§525).
  for (const ch of chunks) {
    if (!kuIds.has(ch.knowledgeUnitId)) violations.push(`orphan chunk ${ch.id} (§525)`);
  }
  // §427: Embeddings without Chunks; orphan embeddings (§525).
  const chunkIds = new Set(chunks.map((c) => c.id));
  for (const em of embeddings) {
    if (!chunkIds.has(em.chunkId)) violations.push(`orphan embedding ${em.id} (§525)`);
  }
  // R-06: citations must key on evidenceId + documentId.
  for (const c of citations) {
    if (!c.evidenceId || !c.documentId) violations.push(`citation ${c.id} missing evidenceId/documentId (R-06)`);
    if (!evidenceIds.has(c.evidenceId)) violations.push(`citation ${c.id} references missing evidence (§525)`);
  }
  return { valid: violations.length === 0, violations };
}

// ===========================================================================
// §148 / §234 — Hardened transactional writer. Single transaction; any failure
// → rollback (partial writes prohibited). Integrity gate runs first.
// ===========================================================================
async function writeRepository(bundle, deps) {
  // Ownership guard for every object class we are about to persist (R-13).
  for (const t of ['document', 'metadata', 'knowledgeUnit', 'evidence', 'citation', 'chunk', 'embedding']) {
    assertRepositoryOwnership(t);
  }

  const integrity = checkIntegrity(bundle);
  if (!integrity.valid) {
    const e = new Error(`Repository integrity check failed: ${integrity.violations.join('; ')}`);
    e.violations = integrity.violations;
    e.stage = 'Integrity';
    throw e; // blocks certification (§525)
  }

  return deps.db.withTransaction(async (tx) => {
    await tx.updateDocumentStatus(bundle.documentId, 'PROCESSED');
    await tx.insertMetadata(bundle.documentId, bundle.metadata || []);
    await tx.insertKnowledgeUnits(bundle.documentId, bundle.knowledgeUnits || []);
    await tx.insertEvidence(bundle.evidence || []);
    await tx.insertCitations(bundle.citations || []);
    await tx.insertChunks(bundle.chunks || []);          // Repository-owned (R-13)
    await tx.insertEmbeddings(bundle.embeddings || []);  // Repository-owned (R-13)
    return {
      committed: true,
      written: {
        knowledgeUnits: (bundle.knowledgeUnits || []).length,
        evidence: (bundle.evidence || []).length,
        citations: (bundle.citations || []).length,
        chunks: (bundle.chunks || []).length,
        embeddings: (bundle.embeddings || []).length,
      },
    };
  });
}

module.exports = {
  REPOSITORY_OWNED,
  FORBIDDEN_IN_REPOSITORY,
  assertRepositoryOwnership,
  checkIntegrity,
  writeRepository,
};
