/**
 * In-memory repository DB fake for Sprint 4 tests.
 * Stands in for the live Supabase datastore (accepted no-live-datastore risk).
 * Exercises the real Sprint 4 repository logic end to end.
 */

'use strict';

const crypto = require('crypto');

function makeRepoDb(seed = {}) {
  const documents = new Map();
  const metadata = [];
  const knowledgeUnits = new Map(); // id -> row
  const evidence = [];
  const citations = [];
  const chunks = [];
  const embeddings = [];
  const relationships = [];
  const processingHistory = [];
  const versions = [];
  let versionCounter = 0;

  if (seed.documents) for (const d of seed.documents) documents.set(d.id, { ...d });

  const api = {
    async findDocumentBySha256(sha) {
      for (const d of documents.values()) if (d.sha256 === sha) return d;
      return null;
    },
    async insertDocument(row) { documents.set(row.id, { ...row }); },
    async updateDocument(id, changes) { const d = documents.get(id); if (d) Object.assign(d, changes); },
    async updateDocumentStatus(id, status) { const d = documents.get(id) || {}; d.id = id; d.status = status; documents.set(id, d); },
    async appendProcessingHistory(rec) {
      processingHistory.push({ id: crypto.randomUUID(), created_at: new Date().toISOString(), ...rec });
    },
    async nextRepositoryVersion(description) {
      versionCounter += 1;
      const v = `repository-v${versionCounter}`;
      versions.push({ id: crypto.randomUUID(), repository_version: v, description, created_at: new Date().toISOString() });
      return v;
    },
    async getKnowledgeUnit(id) { return knowledgeUnits.get(id) || null; },
    async searchMetadata(q) {
      return metadata.filter((m) => (!q.key || m.key === q.key) && (!q.value || m.value === q.value));
    },
    async searchKnowledge(q) {
      return [...knowledgeUnits.values()].filter((k) =>
        (!q.lifecycle_state || k.lifecycle_state === q.lifecycle_state) &&
        (!q.category || k.category === q.category));
    },
    async listChunks() { return chunks.slice(); },
    async replaceEmbeddings(rows) {
      for (const r of rows) {
        const i = embeddings.findIndex((e) => e.chunkId === r.chunkId);
        if (i >= 0) embeddings[i] = { ...embeddings[i], ...r };
        else embeddings.push({ id: crypto.randomUUID(), ...r });
      }
    },
    async withTransaction(fn) {
      const snap = {
        m: metadata.length, e: evidence.length, c: citations.length,
        ch: chunks.length, em: embeddings.length,
        ku: new Map(knowledgeUnits),
        docStatus: new Map([...documents].map(([id, d]) => [id, d.status])),
      };
      const tx = {
        async updateDocumentStatus(id, status) { const d = documents.get(id) || {}; d.id = id; d.status = status; documents.set(id, d); },
        async insertMetadata(docId, rows) { for (const r of rows) metadata.push({ document_id: docId, ...r }); },
        async insertKnowledgeUnits(docId, rows) { for (const r of rows) knowledgeUnits.set(r.id, { document_id: docId, ...r }); },
        async insertEvidence(rows) { for (const r of rows) evidence.push({ ...r }); },
        async insertCitations(rows) { for (const r of rows) citations.push({ ...r }); },
        async insertChunks(rows) { for (const r of rows) chunks.push({ ...r }); },
        async insertEmbeddings(rows) { for (const r of rows) embeddings.push({ ...r }); },
      };
      try { return await fn(tx); }
      catch (err) {
        metadata.length = snap.m; evidence.length = snap.e; citations.length = snap.c;
        chunks.length = snap.ch; embeddings.length = snap.em;
        knowledgeUnits.clear(); for (const [k, v] of snap.ku) knowledgeUnits.set(k, v);
        for (const [id, s] of snap.docStatus) { const d = documents.get(id); if (d) d.status = s; }
        throw err;
      }
    },
    async certificationCounts(documentId) {
      const kus = [...knowledgeUnits.values()].filter((k) => k.document_id === documentId);
      const kuIds = new Set(kus.map((k) => k.id));
      return {
        document: documents.has(documentId) ? 1 : 0,
        knowledgeUnits: kus.length,
        evidence: evidence.filter((e) => kuIds.has(e.knowledgeUnitId)).length,
        citations: citations.filter((c) => c.documentId === documentId).length,
        chunks: chunks.filter((ch) => kuIds.has(ch.knowledgeUnitId)).length,
        embeddings: embeddings.filter((em) => chunks.some((ch) => ch.id === em.chunkId)).length,
      };
    },
    async repositoryAggregates() {
      const kus = [...knowledgeUnits.values()];
      const certified = kus.filter((k) => k.lifecycle_state === 'Certified');
      const chunkIds = new Set(chunks.map((c) => c.id));
      const citedEvidence = new Set(citations.map((c) => c.evidenceId));
      const avgQuality = certified.length
        ? certified.reduce((a, k) => a + (k.quality_score || 0), 0) / certified.length : 0;
      return {
        documents: documents.size,
        certifiedDocuments: [...documents.values()].filter((d) => d.status === 'CERTIFIED').length,
        knowledgeUnits: kus.length,
        certifiedKnowledgeUnits: certified.length,
        duplicateKnowledgeUnits: 0,
        evidence: evidence.length,
        evidenceWithoutCitations: evidence.filter((e) => !citedEvidence.has(e.id)).length,
        citations: citations.length,
        chunks: chunks.length,
        embeddings: embeddings.filter((e) => chunkIds.has(e.chunkId)).length,
        relationships: relationships.length,
        brokenRelationships: 0,
        averageQuality: Math.round(avgQuality * 100) / 100,
        repositorySizeBytes: 0,
        averageVersion: 1,
      };
    },
    _state: { documents, metadata, knowledgeUnits, evidence, citations, chunks, embeddings, processingHistory, versions },
  };
  return api;
}

function makeDeps(overrides = {}) {
  return {
    db: overrides.db || makeRepoDb(),
    embedding: overrides.embedding || {
      async embed(texts, { dimensions }) { return texts.map(() => new Array(dimensions).fill(0.1)); },
    },
  };
}

// A well-formed certified-ingestion bundle (as WF-001 would emit, Sprint 3).
function goodBundle() {
  const documentId = crypto.randomUUID();
  const ku1 = { id: crypto.randomUUID(), statement: 'The Dashboard supports PDF export.', category: 'Feature', authoritySource: 'Manual', sourcePage: 1, sourceParagraph: 1 };
  const ku2 = { id: crypto.randomUUID(), statement: 'The KPI module supports cascading.', category: 'Capability', authoritySource: 'Manual', sourcePage: 1, sourceParagraph: 2 };
  const ev1 = { id: crypto.randomUUID(), knowledgeUnitId: ku1.id, excerpt: ku1.statement, sourcePage: 1 };
  const ev2 = { id: crypto.randomUUID(), knowledgeUnitId: ku2.id, excerpt: ku2.statement, sourcePage: 1 };
  const c1 = { id: crypto.randomUUID(), evidenceId: ev1.id, documentId, page: 1, paragraph: 1 };
  const c2 = { id: crypto.randomUUID(), evidenceId: ev2.id, documentId, page: 1, paragraph: 2 };
  const ch1 = { id: crypto.randomUUID(), knowledgeUnitId: ku1.id, text: ku1.statement, ordinal: 0 };
  const ch2 = { id: crypto.randomUUID(), knowledgeUnitId: ku2.id, text: ku2.statement, ordinal: 0 };
  const em1 = { id: crypto.randomUUID(), chunkId: ch1.id, vector: new Array(1536).fill(0.1), dimensions: 1536 };
  const em2 = { id: crypto.randomUUID(), chunkId: ch2.id, vector: new Array(1536).fill(0.1), dimensions: 1536 };
  return {
    documentId, ocrConfidence: 0.95, createdBy: 'ingestion', changeReason: 'initial',
    metadata: [{ key: 'Product', value: 'CUBES' }],
    knowledgeUnits: [ku1, ku2], evidence: [ev1, ev2], citations: [c1, c2],
    chunks: [ch1, ch2], embeddings: [em1, em2],
  };
}

module.exports = { makeRepoDb, makeDeps, goodBundle };
