/**
 * In-memory adapter fakes for Sprint 3 acceptance tests.
 *
 * These stand in for the real Provider Adapter layer (Sprint 1) and the live
 * Supabase datastore (Sprint 2). The build environment has no live datastore
 * (accepted risk in PROJECT_STATUS: "no live datastore in the build
 * environment"); these fakes exercise the real WF-001/Module-13 logic end to
 * end so the pipeline is provably runnable. They are TEST doubles, not
 * placeholders in the shipped pipeline.
 */

'use strict';

function makeDb() {
  const documents = new Map();      // id -> row
  const bySha = new Map();          // sha256 -> id
  const metadata = [];
  const knowledgeUnits = [];
  const evidence = [];
  const citations = [];
  const chunks = [];
  const embeddings = [];
  const processingHistory = [];     // append-only (R-18)

  const api = {
    async findDocumentBySha256(sha) {
      const id = bySha.get(sha);
      return id ? documents.get(id) : null;
    },
    async insertDocument(row) { documents.set(row.id, { ...row }); bySha.set(row.sha256, row.id); },
    async updateDocumentStatus(id, status) { const d = documents.get(id); if (d) d.status = status; },
    async appendProcessingHistory(rec) {
      processingHistory.push({ id: crypto.randomUUID(), created_at: new Date().toISOString(), ...rec });
    },
    async withTransaction(fn) {
      // snapshot for rollback
      const snap = {
        m: metadata.length, k: knowledgeUnits.length, e: evidence.length,
        c: citations.length, ch: chunks.length, em: embeddings.length,
        docStatus: new Map([...documents].map(([id, d]) => [id, d.status])),
      };
      const tx = {
        async updateDocumentStatus(id, status) { const d = documents.get(id); if (d) d.status = status; },
        async insertMetadata(docId, rows) { for (const r of rows) metadata.push({ document_id: docId, ...r }); },
        async insertKnowledgeUnits(docId, rows) { for (const r of rows) knowledgeUnits.push({ document_id: docId, ...r }); },
        async insertEvidence(rows) { for (const r of rows) evidence.push({ ...r }); },
        async insertCitations(rows) { for (const r of rows) citations.push({ ...r }); },
        async insertChunks(rows) { for (const r of rows) chunks.push({ ...r }); },
        async insertEmbeddings(rows) { for (const r of rows) embeddings.push({ ...r }); },
      };
      try {
        return await fn(tx);
      } catch (err) {
        // rollback (single transaction, §234; WF failure policy Repository->Rollback)
        metadata.length = snap.m; knowledgeUnits.length = snap.k; evidence.length = snap.e;
        citations.length = snap.c; chunks.length = snap.ch; embeddings.length = snap.em;
        for (const [id, s] of snap.docStatus) { const d = documents.get(id); if (d) d.status = s; }
        throw err;
      }
    },
    async certificationCounts(documentId) {
      return {
        document: documents.has(documentId) ? 1 : 0,
        knowledgeUnits: knowledgeUnits.filter((k) => k.document_id === documentId).length,
        evidence: evidence.filter((e) => knowledgeUnits.some((k) => k.id === e.knowledgeUnitId && k.document_id === documentId)).length,
        citations: citations.filter((c) => c.documentId === documentId).length,
        chunks: chunks.filter((ch) => knowledgeUnits.some((k) => k.id === ch.knowledgeUnitId && k.document_id === documentId)).length,
        embeddings: embeddings.filter((em) => chunks.some((ch) => ch.id === em.chunkId)).length,
      };
    },
    _state: { documents, metadata, knowledgeUnits, evidence, citations, chunks, embeddings, processingHistory },
  };
  return api;
}

const crypto = require('crypto');

function makeDeps(overrides = {}) {
  const noopLogger = {
    child() { return noopLogger; },
    info() {}, warn() {}, error() {},
  };
  const db = overrides.db || makeDb();
  return {
    db,
    sleep: () => Promise.resolve(),
    parseJson: (s) => (typeof s === 'string' ? JSON.parse(s) : s),
    logger: overrides.logger || noopLogger,
    telemetry: overrides.telemetry || { record: async () => {}, accumulatedCost: () => 0.0123 },
    prompts: overrides.prompts || {
      async load(id) { return { promptId: id, body: `BODY(${id}) {{ocr}}` }; },
      inject(p, vars) { return p.body.replace('{{ocr}}', vars.ocr || ''); },
    },
    ocr: overrides.ocr || {
      async analyze() {
        return {
          readingOrderPresent: true,
          pages: [{ page: 1, confidence: 0.95, text: 'The Dashboard supports PDF export. The KPI module supports cascading.' }],
        };
      },
    },
    llm: overrides.llm || {
      async complete({ prompt }) {
        if (prompt.startsWith('BODY(PR-002)')) {
          return JSON.stringify({ metadata: [{ key: 'Product', value: 'CUBES' }, { key: 'Language', value: 'English' }] });
        }
        return JSON.stringify({
          knowledgeUnits: [
            { statement: 'The Dashboard supports PDF export.', category: 'Feature', authoritySource: 'Product Manual', sourcePage: 1, sourceParagraph: 1 },
            { statement: 'The KPI module supports cascading.', category: 'Capability', authoritySource: 'Product Manual', sourcePage: 1, sourceParagraph: 2 },
          ],
        });
      },
    },
    embedding: overrides.embedding || {
      async embed(texts, { dimensions }) {
        return texts.map(() => new Array(dimensions).fill(0).map((_, i) => (i % 7) / 7));
      },
    },
  };
}

module.exports = { makeDb, makeDeps };
