/**
 * Sprint 3 acceptance & unit tests.
 * Zero external deps — run with `node tests/acceptance.test.js`.
 *
 * DoD (§ Task Backlog S3): "One uploaded document becomes certified knowledge."
 * Plus coverage of the §154 failure policy, R-06, R-09, and R-18 checkpoints.
 */

'use strict';

const assert = require('assert');
const sw = require('../../workflows/shared/module13_ingestion');
const { runWF001 } = require('../../workflows/shared/WF-001_Knowledge_Ingestion');
const { makeDeps } = require('../fixtures/fakes');

const config = {
  ocr: { endpoint: 'https://x', model: 'prebuilt-layout', timeout: 30000, retryAttempts: 3, minConfidence: 0.7 },
  llm: { knowledgeModel: 'test-llm', metadataModel: 'test-llm' },
  chunking: { maxChars: 1200 },
  embeddings: { provider: 'test', model: 'test-embed', dimensions: 1536, batchSize: 16 },
};

const FIXTURE = Buffer.from('%PDF-1.4 fixture CUBES product manual — dashboard + KPI', 'utf8');

let passed = 0, failed = 0;
async function test(name, fn) {
  try { await fn(); console.log(`  PASS  ${name}`); passed++; }
  catch (err) { console.error(`  FAIL  ${name}\n        ${err.message}`); failed++; }
}

(async () => {
  console.log('Sprint 3 — Knowledge Ingestion tests\n');

  // --- Node-level -----------------------------------------------------------
  await test('SW-001 generates a UUID correlation id', () => {
    const { correlationId } = sw.sw001_generateCorrelationId();
    assert.match(correlationId, /^[0-9a-f-]{36}$/);
  });

  await test('SW-002 is deterministic (same bytes -> same hash)', () => {
    const a = sw.sw002_generateSha256(FIXTURE).sha256;
    const b = sw.sw002_generateSha256(FIXTURE).sha256;
    assert.strictEqual(a, b);
    assert.strictEqual(a.length, 64);
  });

  await test('SW-010 citations key on evidenceId + documentId (R-06)', () => {
    const { citations } = sw.sw010_citationGenerator({
      evidence: [{ id: 'ev1', sourcePage: 1, sourceParagraph: 2 }],
      documentId: 'doc1',
    });
    assert.strictEqual(citations[0].evidenceId, 'ev1');
    assert.strictEqual(citations[0].documentId, 'doc1');
  });

  await test('SW-010 rejects missing documentId (R-06)', () => {
    assert.throws(() => sw.sw010_citationGenerator({ evidence: [{ id: 'e' }] }), /documentId/);
  });

  await test('SW-011 rejects invalid category, keeps valid (R-05)', () => {
    const ku = [
      { id: 'k1', statement: 'valid', category: 'Feature' },
      { id: 'k2', statement: 'bad', category: 'NotARealCategory' },
    ];
    const ev = [{ id: 'e1', knowledgeUnitId: 'k1' }, { id: 'e2', knowledgeUnitId: 'k2' }];
    const ci = [{ evidenceId: 'e1' }, { evidenceId: 'e2' }];
    const r = sw.sw011_knowledgeValidator({ knowledgeUnits: ku, evidence: ev, citations: ci });
    assert.strictEqual(r.accepted.length, 1);
    assert.strictEqual(r.accepted[0].id, 'k1');
    assert.ok(r.rejected[0].reasons.some((x) => /invalid category/.test(x)));
  });

  await test('SW-011 rejects duplicate + missing-citation units', () => {
    const ku = [
      { id: 'k1', statement: 'same', category: 'Feature' },
      { id: 'k2', statement: 'same', category: 'Feature' },      // duplicate
      { id: 'k3', statement: 'no cite', category: 'Feature' },   // missing citation
    ];
    const ev = [{ id: 'e1', knowledgeUnitId: 'k1' }, { id: 'e2', knowledgeUnitId: 'k2' }, { id: 'e3', knowledgeUnitId: 'k3' }];
    const ci = [{ evidenceId: 'e1' }, { evidenceId: 'e2' }]; // none for e3
    const r = sw.sw011_knowledgeValidator({ knowledgeUnits: ku, evidence: ev, citations: ci });
    assert.strictEqual(r.accepted.length, 1);
    assert.strictEqual(r.rejected.length, 2);
  });

  await test('SW-012 never chunks below atomic KU; splits only oversize', () => {
    const long = 'x'.repeat(2500);
    const r = sw.sw012_chunkBuilder({ acceptedUnits: [
      { id: 'k1', statement: 'short' }, { id: 'k2', statement: long },
    ] }, config);
    const k1 = r.chunks.filter((c) => c.knowledgeUnitId === 'k1');
    const k2 = r.chunks.filter((c) => c.knowledgeUnitId === 'k2');
    assert.strictEqual(k1.length, 1);
    assert.ok(k2.length >= 2);
  });

  await test('SW-013 enforces vector(1536) dimension (R-09)', async () => {
    const deps = makeDeps();
    const r = await sw.sw013_embeddingGenerator({ chunks: [{ id: 'c1', text: 'hi' }] }, deps, config);
    assert.strictEqual(r.embeddings[0].dimensions, 1536);
    assert.strictEqual(r.embeddings[0].vector.length, 1536);
  });

  await test('SW-013 throws on dimension mismatch (R-09)', async () => {
    const deps = makeDeps({ embedding: { async embed(t) { return t.map(() => new Array(768).fill(0)); } } });
    await assert.rejects(
      sw.sw013_embeddingGenerator({ chunks: [{ id: 'c1', text: 'hi' }] }, deps, config),
      /dimension 768 != configured 1536/,
    );
  });

  await test('SW-005 retries OCR up to 3 times then fails', async () => {
    let calls = 0;
    const deps = makeDeps({ ocr: { async analyze() { calls++; throw new Error('boom'); } } });
    await assert.rejects(sw.sw005_azureOcr(FIXTURE, deps, config), /failed after 3 attempts/);
    assert.strictEqual(calls, 3);
  });

  // --- WF-001 end to end (the DoD) -----------------------------------------
  await test('WF-001: one uploaded document becomes CERTIFIED knowledge (DoD)', async () => {
    const deps = makeDeps();
    const res = await runWF001({ binary: FIXTURE, filename: 'manual.pdf' }, deps, config);
    assert.strictEqual(res.status, 'CERTIFIED');
    assert.strictEqual(res.certification.certified, true);
    assert.strictEqual(res.summary.knowledgeUnits, 2);
    assert.strictEqual(res.summary.evidenceObjects, 2);
    assert.ok(res.summary.chunks >= 2);
    assert.strictEqual(res.summary.embeddings, res.summary.chunks);
    const doc = deps.db._state.documents.get(res.documentId);
    assert.strictEqual(doc.status, 'CERTIFIED');
  });

  await test('WF-001: writes processing_history checkpoints per stage (R-18)', async () => {
    const deps = makeDeps();
    const res = await runWF001({ binary: FIXTURE }, deps, config);
    const stages = new Set(deps.db._state.processingHistory.map((h) => h.stage));
    for (const s of ['Upload', 'OCR', 'KnowledgeExtraction', 'ChunkGeneration', 'Embeddings', 'Certification']) {
      assert.ok(stages.has(s), `missing checkpoint stage: ${s}`);
    }
    // certification completed
    const cert = deps.db._state.processingHistory.find((h) => h.stage === 'Certification' && h.status === 'COMPLETED');
    assert.ok(cert, 'certification COMPLETED checkpoint missing');
    void res;
  });

  await test('WF-001: duplicate document stops the workflow (§154)', async () => {
    const deps = makeDeps();
    await runWF001({ binary: FIXTURE }, deps, config);              // first ingest
    const res2 = await runWF001({ binary: FIXTURE }, deps, config); // same bytes
    assert.strictEqual(res2.status, 'DUPLICATE');
    // only one document persisted
    assert.strictEqual(deps.db._state.documents.size, 1);
  });

  await test('WF-001: OCR failure -> HUMAN_REVIEW, no knowledge written', async () => {
    const deps = makeDeps({ ocr: { async analyze() { throw new Error('ocr down'); } } });
    const res = await runWF001({ binary: FIXTURE }, deps, config);
    assert.strictEqual(res.status, 'FAILED');
    assert.strictEqual(res.stage, 'OCR');
    const doc = deps.db._state.documents.get(res.documentId);
    assert.strictEqual(doc.status, 'HUMAN_REVIEW');
    assert.strictEqual(deps.db._state.knowledgeUnits.length, 0);
  });

  await test('WF-001: extraction failure -> HUMAN_REVIEW (§154)', async () => {
    const deps = makeDeps({ llm: { async complete() { throw new Error('llm error'); } } });
    const res = await runWF001({ binary: FIXTURE }, deps, config);
    assert.strictEqual(res.status, 'FAILED');
    const doc = deps.db._state.documents.get(res.documentId);
    assert.strictEqual(doc.status, 'HUMAN_REVIEW');
  });

  await test('WF-001: repository write failure rolls back (§154)', async () => {
    const deps = makeDeps();
    const orig = deps.db.withTransaction.bind(deps.db);
    deps.db.withTransaction = async () => { throw new Error('db write failed'); };
    const res = await runWF001({ binary: FIXTURE }, deps, config);
    assert.strictEqual(res.status, 'FAILED');
    assert.strictEqual(res.stage, 'Repository');
    assert.strictEqual(deps.db._state.knowledgeUnits.length, 0); // nothing persisted
    void orig;
  });

  await test('WF-001: emits §216 execution summary shape', async () => {
    const deps = makeDeps();
    const res = await runWF001({ binary: FIXTURE }, deps, config);
    for (const k of ['workflow', 'executionId', 'status', 'duration', 'documentsProcessed',
      'knowledgeUnits', 'evidenceObjects', 'chunks', 'embeddings', 'cost']) {
      assert.ok(k in res.summary, `summary missing ${k}`);
    }
    assert.strictEqual(res.summary.workflow, 'WF-001');
  });

  console.log(`\n${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
})();
