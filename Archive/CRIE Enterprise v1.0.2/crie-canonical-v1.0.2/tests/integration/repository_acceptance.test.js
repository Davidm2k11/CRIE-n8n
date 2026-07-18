/**
 * Sprint 4 acceptance & unit tests. Run: node tests/acceptance.test.js
 *
 * DoD (Task Backlog S4): Production repository operational; certification
 * passes; APIs, health, and statistics available. Repository never bypassed.
 */

'use strict';

const assert = require('assert');
const cert = require('../../workflows/shared/repository_certification');
const writer = require('../../workflows/shared/repository_writer');
const hs = require('../../workflows/shared/repository_health_statistics');
const { createRepositoryApi } = require('../../workflows/shared/repository_api');
const { makeDeps, makeRepoDb, goodBundle } = require('../fixtures/repository_fakes');

const config = {
  repository: {
    qualityThreshold: 0.6,
    healthThresholds: { healthy: 85, degraded: 60 },
  },
  embeddings: { provider: 'test', model: 'test-embed', dimensions: 1536, batchSize: 16 },
};

let passed = 0, failed = 0;
async function test(name, fn) {
  try { await fn(); console.log(`  PASS  ${name}`); passed++; }
  catch (err) { console.error(`  FAIL  ${name}\n        ${err.stack || err.message}`); failed++; }
}

(async () => {
  console.log('Sprint 4 — Repository tests\n');

  // --- §511 quality score ---------------------------------------------------
  await test('§511 quality score is 0..1 and rewards complete units', () => {
    const good = cert.computeQualityScore(
      { statement: 'The Dashboard supports PDF export.', category: 'Feature', sourcePage: 1, sourceParagraph: 1 },
      { ocrConfidence: 0.95, citationCount: 1, duplicateProbability: 0 }, config);
    const poor = cert.computeQualityScore(
      { statement: '', category: 'BadCat' },
      { ocrConfidence: 0.2, citationCount: 0, duplicateProbability: 0.9 }, config);
    assert.ok(good > 0.8 && good <= 1);
    assert.ok(poor < 0.3);
  });

  // --- §512 per-unit certification -----------------------------------------
  await test('§512 certifies a complete unit; rejects invalid category (R-05)', () => {
    const okCtx = { ocrConfidence: 0.95, evidenceCount: 1, citationCount: 1, isDuplicate: false };
    const r1 = cert.certifyKnowledgeUnit({ id: 'k1', statement: 'x'.repeat(30), category: 'Feature', authoritySource: 'Manual', sourcePage: 1, sourceParagraph: 1 }, okCtx, config);
    assert.strictEqual(r1.certified, true);
    assert.strictEqual(r1.lifecycleState, 'Certified');
    const r2 = cert.certifyKnowledgeUnit({ id: 'k2', statement: 'x'.repeat(30), category: 'Nope', authoritySource: 'Manual' }, okCtx, config);
    assert.strictEqual(r2.certified, false);
    assert.strictEqual(r2.checks.validCategory, false);
    assert.strictEqual(r2.reviewRequired, true);
  });

  await test('§512 rejects unit missing citation (R-06) or authority (§525)', () => {
    const noCite = cert.certifyKnowledgeUnit({ id: 'k', statement: 'x'.repeat(30), category: 'Feature', authoritySource: 'M' },
      { ocrConfidence: 0.9, evidenceCount: 1, citationCount: 0, isDuplicate: false }, config);
    assert.strictEqual(noCite.checks.citationExists, false);
    const noAuth = cert.certifyKnowledgeUnit({ id: 'k', statement: 'x'.repeat(30), category: 'Feature' },
      { ocrConfidence: 0.9, evidenceCount: 1, citationCount: 1, isDuplicate: false }, config);
    assert.strictEqual(noAuth.checks.authorityAssigned, false);
  });

  // --- §519 versioning + lineage -------------------------------------------
  await test('§519 buildVersionedUnit links previous_version + records lineage', () => {
    const prev = { id: 'old-id' };
    const v = cert.buildVersionedUnit({ id: 'new-id', statement: 's', category: 'Feature' }, prev, { createdBy: 'u', changeReason: 'update' });
    assert.strictEqual(v.previous_version, 'old-id');
    assert.strictEqual(v.created_by, 'u');
    assert.strictEqual(v.change_reason, 'update');
    assert.strictEqual(v.lifecycle_state, 'Certified');
  });

  await test('§522 deprecateUnit never deletes; marks Deprecated', () => {
    const d = cert.deprecateUnit({ id: 'k', lifecycle_state: 'Certified' }, { changeReason: 'superseded' });
    assert.strictEqual(d.lifecycle_state, 'Deprecated');
  });

  // --- §524/§525/§427 integrity + governance -------------------------------
  await test('§524 integrity passes on a well-formed bundle', () => {
    const b = goodBundle();
    const r = writer.checkIntegrity(b);
    assert.strictEqual(r.valid, true, JSON.stringify(r.violations));
  });

  await test('§427 rejects evidence without citation', () => {
    const b = goodBundle();
    b.citations = b.citations.slice(0, 1); // drop one citation
    const r = writer.checkIntegrity(b);
    assert.strictEqual(r.valid, false);
    assert.ok(r.violations.some((v) => /no citation/.test(v)));
  });

  await test('§525 rejects orphan embedding + knowledge without authority', () => {
    const b = goodBundle();
    b.embeddings.push({ id: 'orphan', chunkId: 'missing', vector: [], dimensions: 1536 });
    b.knowledgeUnits[0].authoritySource = null;
    const r = writer.checkIntegrity(b);
    assert.ok(r.violations.some((v) => /orphan embedding/.test(v)));
    assert.ok(r.violations.some((v) => /no authority/.test(v)));
  });

  // --- R-13 / §425 ownership ------------------------------------------------
  await test('R-13 ownership guard rejects Compliance Result + Context Package', () => {
    assert.throws(() => writer.assertRepositoryOwnership('complianceResult'), /NEVER be stored/);
    assert.throws(() => writer.assertRepositoryOwnership('contextPackage'), /NEVER be stored/);
    assert.throws(() => writer.assertRepositoryOwnership('prompt'), /NEVER be stored/);
    assert.strictEqual(writer.assertRepositoryOwnership('chunk'), true);      // owned (R-13)
    assert.strictEqual(writer.assertRepositoryOwnership('embedding'), true);  // owned (R-13)
  });

  // --- §148 transaction -----------------------------------------------------
  await test('§148 writer commits a valid bundle in one transaction', async () => {
    const deps = makeDeps();
    const b = goodBundle();
    // mark units certified before write (writer persists what API certifies)
    b.knowledgeUnits = b.knowledgeUnits.map((k) => ({ ...k, lifecycle_state: 'Certified' }));
    const r = await writer.writeRepository(b, deps);
    assert.strictEqual(r.committed, true);
    assert.strictEqual(deps.db._state.knowledgeUnits.size, 2);
  });

  await test('§148 integrity failure blocks write (nothing persisted)', async () => {
    const deps = makeDeps();
    const b = goodBundle();
    b.citations = []; // integrity violation
    await assert.rejects(writer.writeRepository(b, deps), /integrity check failed/);
    assert.strictEqual(deps.db._state.knowledgeUnits.size, 0);
  });

  // --- §528 health ----------------------------------------------------------
  await test('§528 health score 0..100 with status bands', () => {
    const healthy = hs.computeHealthScore({
      documents: 2, certifiedDocuments: 2, knowledgeUnits: 10, certifiedKnowledgeUnits: 10,
      duplicateKnowledgeUnits: 0, evidence: 10, evidenceWithoutCitations: 0, citations: 10,
      chunks: 10, embeddings: 10, relationships: 0, brokenRelationships: 0,
    }, config);
    assert.strictEqual(healthy.status, 'Healthy');
    assert.ok(healthy.score >= 85 && healthy.score <= 100);
    const bad = hs.computeHealthScore({
      documents: 4, certifiedDocuments: 1, knowledgeUnits: 10, certifiedKnowledgeUnits: 2,
      duplicateKnowledgeUnits: 5, evidence: 10, evidenceWithoutCitations: 6, citations: 4,
      chunks: 10, embeddings: 2, relationships: 0, brokenRelationships: 0,
    }, config);
    assert.notStrictEqual(bad.status, 'Healthy');
  });

  // --- §529 statistics ------------------------------------------------------
  await test('§529 statistics expose all required fields', () => {
    const stats = hs.computeStatistics({
      documents: 1, knowledgeUnits: 2, evidence: 2, citations: 2, chunks: 2, embeddings: 2,
      averageQuality: 0.9, repositorySizeBytes: 100, averageVersion: 1,
    }, { score: 92 });
    for (const k of ['documents', 'knowledgeUnits', 'evidenceObjects', 'citations',
      'retrievalChunks', 'embeddings', 'averageQuality', 'repositorySizeBytes',
      'averageVersion', 'repositoryHealth']) {
      assert.ok(k in stats, `stats missing ${k}`);
    }
    assert.strictEqual(stats.repositoryHealth, 92);
  });

  // --- Repository API end to end (the DoD) ---------------------------------
  await test('API createDocument certifies + persists a full bundle (DoD)', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    const b = goodBundle();
    const res = await api.createDocument(b);
    assert.strictEqual(res.status, 'OK');
    assert.strictEqual(res.data.certification.certified, true);
    assert.ok(res.data.repositoryVersion.startsWith('repository-v'));
    assert.strictEqual(deps.db._state.knowledgeUnits.size, 2);
    const doc = deps.db._state.documents.get(b.documentId);
    assert.strictEqual(doc.status, 'CERTIFIED');
  });

  await test('API createDocument fails cleanly when no unit is certifiable', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    const b = goodBundle();
    b.knowledgeUnits = b.knowledgeUnits.map((k) => ({ ...k, category: 'BadCat', authoritySource: null }));
    const res = await api.createDocument(b);
    assert.strictEqual(res.status, 'ERROR');
    assert.strictEqual(res.error.code, 'NO_CERTIFIABLE_KNOWLEDGE');
    assert.strictEqual(deps.db._state.knowledgeUnits.size, 0); // nothing persisted
  });

  await test('API getKnowledgeUnit returns certified-only (§518)', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    await api.createDocument(goodBundle());
    const anyId = [...deps.db._state.knowledgeUnits.keys()][0];
    const okRes = await api.getKnowledgeUnit(anyId);
    assert.strictEqual(okRes.status, 'OK');
    // a draft unit is not surfaced
    deps.db._state.knowledgeUnits.get(anyId).lifecycle_state = 'Draft';
    const draftRes = await api.getKnowledgeUnit(anyId);
    assert.strictEqual(draftRes.error.code, 'NOT_CERTIFIED');
  });

  await test('API searchKnowledge only returns Certified units', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    await api.createDocument(goodBundle());
    const res = await api.searchKnowledge({ category: 'Feature' });
    assert.strictEqual(res.status, 'OK');
    assert.ok(res.data.every((k) => k.lifecycle_state === 'Certified'));
  });

  await test('API rebuildEmbeddings refuses non-reserved reason (§523)', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    const denied = await api.rebuildEmbeddings({ reason: 'because' });
    assert.strictEqual(denied.error.code, 'NOT_ALLOWED');
  });

  await test('API rebuildEmbeddings allows reserved reason + enforces 1536 (R-09)', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    await api.createDocument(goodBundle());
    const res = await api.rebuildEmbeddings({ reason: 'EmbeddingModelChange' });
    assert.strictEqual(res.status, 'OK');
    assert.strictEqual(res.data.regenerated, 2);
  });

  await test('API health + statistics available and consistent', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    await api.createDocument(goodBundle());
    const h = await api.repositoryHealth();
    const s = await api.repositoryStatistics();
    assert.strictEqual(h.status, 'OK');
    assert.ok(h.data.score >= 0 && h.data.score <= 100);
    assert.strictEqual(s.data.knowledgeUnits, 2);
    assert.strictEqual(s.data.repositoryHealth, h.data.score);
  });

  await test('API archiveDocument never deletes; keeps recoverable (§530/§531)', async () => {
    const deps = makeDeps();
    const api = createRepositoryApi(deps, config);
    const b = goodBundle();
    await api.createDocument(b);
    const res = await api.archiveDocument(b.documentId);
    assert.strictEqual(res.data.status, 'ARCHIVED');
    assert.strictEqual(res.data.recoverable, true);
    assert.strictEqual(deps.db._state.knowledgeUnits.size, 2); // knowledge preserved
  });

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
})();
