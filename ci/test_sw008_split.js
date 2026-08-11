#!/usr/bin/env node
/**
 * test_sw008_split.js — behavioural test for SW-008's adaptive finish_reason=length handling.
 *
 * WHY THIS EXISTS
 * ---------------
 * A single dense batch used to abort the whole document: collect() threw on
 * finish_reason=length, discarding every batch that had already succeeded. On the Arabic
 * manual that cost two full extraction runs (~$1.11 of wasted OpenAI spend) before the batch
 * size was tuned by hand. SW-008 now splits the offending batch and retries the halves in
 * place. This test proves that path WITHOUT calling a model.
 *
 * HOW IT WORKS
 * ------------
 * It executes the REAL collect() source, read straight out of the deployed workflow artifact,
 * in a sandbox that supplies n8n's `$json` / `$(...)` bindings. Nothing is re-implemented, so
 * the test cannot drift from what actually runs: if collect() changes, this exercises the
 * change. A fake "model" decides finish_reason from batch composition, which lets us provoke
 * truncation deterministically and for free.
 *
 * Exit 0 = all assertions pass, 1 = failure.
 */
'use strict';
const fs = require('fs');
const path = require('path');

const WF = path.join(__dirname, '..', 'workflows', 'subworkflows', 'WF-001 SWs',
                     'SW-008 LLM Knowledge.json');
const COLLECT = 'collect() — Validate + Accumulate';

const wf = JSON.parse(fs.readFileSync(WF, 'utf8'));
const node = wf.nodes.find((n) => n.name === COLLECT);
if (!node) { console.error('FATAL: node not found: ' + COLLECT); process.exit(1); }
const SRC = node.parameters.jsCode;

const SETTINGS = { tokensPerUnit: 55, tpmBudget: 30000, maxPacingMs: 55000,
                   maxBatches: 200, maxSplitDepth: 4 };

/** Run the real collect() with n8n's bindings stubbed. */
function runCollect({ bx, batchMarker, response, settings = SETTINGS, quiet = true }) {
  const nodes = {
    'build-request() — Render Batch': { _bx: bx, _batchMarker: batchMarker },
    'When Executed by WF-001': { documentId: 'DOC-TEST', correlationId: 'CID-TEST' },
    'Load PR-001 + LLM Settings': { settings },
  };
  const $ = (name) => {
    if (!(name in nodes)) throw new Error('test stub: unexpected node reference ' + name);
    return { first: () => ({ json: nodes[name] }) };
  };
  const sandboxConsole = quiet ? { log: () => {} } : console;
  const fn = new Function('$', '$json', 'console', SRC);
  return fn($, response, sandboxConsole);
}

/** A batch in the lean shape plan() emits. */
const mkBatch = (index, first, last, extra = {}) => Object.assign({
  index, headingBreadcrumb: 'S1', estimatedTokens: (last - first + 1) * 40,
  expectedCompletionTokens: Math.ceil((last - first + 1) * 1.2 * 55),
  firstParagraph: first, lastParagraph: last, overlapFrom: null,
  newParagraphs: last - first + 1,
  paragraphIndexes: Array.from({ length: last - first + 1 }, (_, k) => first + k),
  splitParts: [],
}, extra);

const mkState = (batches) => ({
  batches, planStats: { totalBatches: batches.length }, cursor: 0, results: [], rejected: [],
  paragraphRoles: {}, pacingMs: 0, requestMaxTokens: 16384, completionTarget: 8192,
  plannedDensity: 1.2, tpmBudget: 30000,
});

const truncated = (completion) => ({
  statusCode: 200,
  body: { choices: [{ finish_reason: 'length', message: { content: '{"knowledgeUnits":[{"stat' } }],
          usage: { prompt_tokens: 5000, completion_tokens: completion, total_tokens: 5000 + completion } },
});
const ok = (paragraphIndexes) => ({
  statusCode: 200,
  body: {
    choices: [{ finish_reason: 'stop', message: { content: JSON.stringify({
      knowledgeUnits: paragraphIndexes.map((p) => ({
        statement: 'unit from paragraph ' + p, category: 'Feature',
        authoritySource: 'Official SRS', sourcePage: 1, sourceParagraph: p })) }) } }],
    usage: { prompt_tokens: 5000, completion_tokens: 2000, total_tokens: 7000 },
  },
});

/**
 * Drive the loop the way WF-001 does: send the batch at the cursor, feed the fake model's
 * verdict to collect(), repeat. `isDense` decides which batches truncate.
 */
function drive(state, isDense, { maxIterations = 200, settings = SETTINGS } = {}) {
  let bx = state, calls = 0, splits = 0;
  const sent = [];
  for (let i = 0; i < maxIterations; i++) {
    if (bx.cursor >= bx.batches.length) return { bx, calls, splits, sent, completed: true };
    const batch = bx.batches[bx.cursor];
    const before = bx.batches.length;
    calls++;
    sent.push({ index: batch.index, paragraphs: batch.paragraphIndexes.slice() });
    const res = isDense(batch) ? truncated(16384) : ok(batch.paragraphIndexes);
    const out = runCollect({ bx, batchMarker: batch.index, response: res, settings });
    bx = out[0].json._bx;
    if (bx.batches.length > before) splits++;
  }
  throw new Error('loop did not terminate within ' + maxIterations + ' iterations');
}

let pass = 0, fail = 0;
const check = (label, cond, detail) => {
  if (cond) { pass++; console.log('  PASS  ' + label); }
  else { fail++; console.log('  FAIL  ' + label + (detail ? '\n        ' + detail : '')); }
};

console.log('='.repeat(74));
console.log('SW-008 adaptive finish_reason=length — behavioural test');
console.log('='.repeat(74));

// ---------------------------------------------------------------- 1: no split
console.log('\n1. A batch that fits makes exactly one call and advances');
{
  const r = drive(mkState([mkBatch(1, 1, 10), mkBatch(2, 11, 20)]), () => false);
  check('completed', r.completed);
  check('one call per batch (2)', r.calls === 2, 'calls=' + r.calls);
  check('no splits', r.splits === 0 && !(r.bx.splits || []).length);
  check('two result sets', r.bx.results.length === 2);
  check('batch count unchanged', r.bx.batches.length === 2);
}

// ------------------------------------------------------- 2: one split, depth 1
console.log('\n2. A dense batch splits and both halves are retried');
{
  // Paragraphs 11-20 are dense: a batch holding more than 6 of them truncates. The threshold
  // is 6 rather than 3 so that ONE split is sufficient — a 10-paragraph batch fails, its
  // 5-paragraph halves fit. (At >3 the halves still fail and it legitimately splits twice,
  // which is what case 3 covers.)
  const dense = (b) => b.paragraphIndexes.filter((p) => p >= 11 && p <= 20).length > 6;
  const r = drive(mkState([mkBatch(1, 1, 10), mkBatch(2, 11, 20)]), dense);
  check('completed', r.completed);
  check('split recorded once', (r.bx.splits || []).length === 1,
        JSON.stringify(r.bx.splits));
  check('batches grew 2 -> 3', r.bx.batches.length === 3);
  const sp = r.bx.splits[0];
  check('split telemetry has parent/depth/tokens',
        sp.parentIndex === 2 && sp.depth === 1 && sp.completionTokens === 16384 && sp.maxTokens === 16384,
        JSON.stringify(sp));
  check('child indexes are ordered and unique (2, 2.5)',
        r.bx.batches.map((b) => b.index).join(',') === '1,2,2.5',
        r.bx.batches.map((b) => b.index).join(','));
  const covered = r.bx.results.flatMap((x) => x.knowledgeUnits.map((k) => k.sourceParagraph));
  check('all 20 paragraphs represented exactly once',
        covered.length === 20 && new Set(covered).size === 20 &&
        Math.min(...covered) === 1 && Math.max(...covered) === 20,
        'covered=' + covered.length + ' unique=' + new Set(covered).size);
  check('ordering preserved', JSON.stringify(covered) === JSON.stringify([...covered].sort((a, b) => a - b)));
  const dead = r.sent.filter((s) => s.index === 2 && s.paragraphs.length === 10).length;
  check('the failing batch was sent once, not repeatedly', dead === 1, 'sent ' + dead + 'x');
}

// ------------------------------------------------- 3: recursive split, depth 2
console.log('\n3. A half that is still too dense splits again');
{
  const dense = (b) => b.paragraphIndexes.filter((p) => p >= 21 && p <= 30).length > 3;
  const r = drive(mkState([mkBatch(1, 1, 20), mkBatch(2, 21, 40)]), dense);
  check('completed', r.completed);
  check('two or more splits', (r.bx.splits || []).length >= 2, JSON.stringify(r.bx.splits));
  check('reached depth 2', Math.max(...r.bx.splits.map((s) => s.depth)) >= 2);
  const covered = r.bx.results.flatMap((x) => x.knowledgeUnits.map((k) => k.sourceParagraph));
  check('all 40 paragraphs represented exactly once',
        covered.length === 40 && new Set(covered).size === 40,
        'covered=' + covered.length + ' unique=' + new Set(covered).size);
  check('ordering preserved', JSON.stringify(covered) === JSON.stringify([...covered].sort((a, b) => a - b)));
  const idx = r.bx.batches.map((b) => b.index);
  check('indexes strictly increasing', idx.every((v, i) => i === 0 || v > idx[i - 1]), idx.join(','));
}

// --------------------------------------------- 4: bounded failure — depth limit
console.log('\n4. Always-dense content fails loudly at maxSplitDepth (no silent drop)');
{
  let threw = null;
  try {
    drive(mkState([mkBatch(1, 1, 64)]), () => true, { settings: { ...SETTINGS, maxSplitDepth: 3 } });
  } catch (e) { threw = e.message; }
  check('threw', !!threw, String(threw));
  check('names maxSplitDepth and refuses to drop content',
        !!threw && /maxSplitDepth=3/.test(threw) && /Refusing to drop content/.test(threw), String(threw));
}

// ------------------------------------ 5: bounded failure — single paragraph
console.log('\n5. A single paragraph that cannot fit fails loudly rather than splitting');
{
  let threw = null;
  try { drive(mkState([mkBatch(1, 7, 7)]), () => true); } catch (e) { threw = e.message; }
  check('threw', !!threw, String(threw));
  check('identifies the single paragraph and refuses to drop it',
        !!threw && /SINGLE paragraph \(7\)/.test(threw) && /Refusing to drop content/.test(threw),
        String(threw));
}

// --------------------------------------------- 6: oversized split-parts stay together
console.log('\n6. A paragraph split into parts is never cut across children');
{
  // paragraph 5 arrives as three parts; it must land wholly in one child.
  const b = mkBatch(1, 1, 8);
  b.paragraphIndexes = [1, 2, 3, 4, 5, 5, 5, 6, 7, 8];
  b.splitParts = [1, 2, 3].map((part) => ({ index: 5, part, partsTotal: 3, text: 'part ' + part }));
  let calls = 0;
  const r = drive(mkState([b]), () => (calls++ === 0));   // truncate only the first call
  check('completed', r.completed);
  const kids = r.bx.batches.filter((x) => x.splitDepth === 1);
  check('two children', kids.length === 2, JSON.stringify(kids.map((k) => k.paragraphIndexes)));
  const withFive = kids.filter((k) => k.paragraphIndexes.includes(5));
  check('paragraph 5 lives in exactly one child', withFive.length === 1);
  check('all three parts travel with it',
        withFive[0].paragraphIndexes.filter((i) => i === 5).length === 3 &&
        withFive[0].splitParts.length === 3,
        JSON.stringify(withFive[0].splitParts));
  const otherChild = kids.find((k) => !k.paragraphIndexes.includes(5));
  check('the other child carries no stray parts for it', otherChild.splitParts.length === 0);
  const total = kids.reduce((a, k) => a + k.paragraphIndexes.length, 0);
  check('membership conserved (10 entries)', total === 10, 'total=' + total);
}

// ------------------------------------------------- 7: earlier results survive
console.log('\n7. Batches that already succeeded are neither lost nor re-sent');
{
  const dense = (b) => b.paragraphIndexes.some((p) => p >= 21 && p <= 30) &&
                       b.paragraphIndexes.length > 5;
  const r = drive(mkState([mkBatch(1, 1, 10), mkBatch(2, 11, 20), mkBatch(3, 21, 30)]), dense);
  check('completed', r.completed);
  const b1 = r.sent.filter((s) => s.index === 1).length;
  const b2 = r.sent.filter((s) => s.index === 2).length;
  check('batch 1 sent exactly once', b1 === 1, 'sent ' + b1 + 'x');
  check('batch 2 sent exactly once', b2 === 1, 'sent ' + b2 + 'x');
  const covered = r.bx.results.flatMap((x) => x.knowledgeUnits.map((k) => k.sourceParagraph));
  check('all 30 paragraphs represented exactly once',
        covered.length === 30 && new Set(covered).size === 30,
        'covered=' + covered.length);
}

console.log('\n' + '='.repeat(74));
if (fail) { console.log('FAILED — ' + pass + ' passed, ' + fail + ' failed.'); process.exit(1); }
console.log('PASSED — ' + pass + ' assertions.');
process.exit(0);
