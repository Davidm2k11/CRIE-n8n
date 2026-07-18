# Sprint 5 — Commit & Tag

## Commit message

```
feat(retrieval): Sprint 5 — WF-002 canonical §452 retrieval pipeline (v0.6.0)

Implement WF-002 Enterprise Retrieval as the canonical §452 pipeline (R-12)
via SW-016…SW-021, emitting the Context Package contract (§294/§76) — the only
object accepted by WF-003.

Backlog: S5-1…S5-15 (all complete)

- SW-016 Requirement Analyzer: normalization (§453), acronym/synonym expansion
  (§453/§455), metadata expansion (§454), strategy selection (§456)
- SW-017 Metadata Filter (§257/§457), Certified-only default
- SW-018 Hybrid Retriever: keyword FTS/trigram/BM25 (§458) + semantic pgvector
  cosine (§459) + candidate merge (§460), independent scoring (§461)
- Composite ranking (§462, configurable), authority ranking (§439/§464, 9-source
  per R-16), freshness (§463, never overrides authority), dedup (§466)
- SW-019 Cross-Encoder Reranker (§259/§465), gated by rerankerEnabled (R-12/§305)
- SW-020 Conflict Detector (§260/§467): conflicts preserved, never hidden
- SW-021 Context Builder: deterministic compression (§468), token budget (§469),
  context quality (§470)
- Context validation (§74) + empty-retrieval ladder (§471); LLM never called
- Context Package contract (union of §76/§187/§294; schemaVersion 1.1, §296)
- Authored config (R-08): retrieval.yaml, authority.yaml; dictionary/authority
  seed SQL for 0021 (§444–445) + §439
- Importable n8n JSON: WF-002 master + SW-016…SW-021
- 18/18 Sprint 5 acceptance tests passing; non-bypass telemetry (§599/§608)

Exit gate: valid Context Package produced and validated — MET.
No Sprint 6 work; no future-sprint placeholders; architecture unchanged.

Refs: R-08, R-09, R-12, R-16; §256–261, §294, §439, §452–472, §74, §305
License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
```

## Files changed / added

```
config/retrieval.yaml
config/authority.yaml
contracts/context_package.contract.json
src/retrieval/__init__.py
src/retrieval/adapters.py
src/retrieval/analyze.py
src/retrieval/rank.py
src/retrieval/context.py
src/retrieval/pipeline.py
workflows/master/WF-002_Enterprise_Retrieval.json
workflows/sub/SW-016_Requirement_Analyzer.json
workflows/sub/SW-017_Metadata_Filter.json
workflows/sub/SW-018_Hybrid_Retriever.json
workflows/sub/SW-019_Cross_Encoder_Reranker.json
workflows/sub/SW-020_Conflict_Detector.json
workflows/sub/SW-021_Context_Builder.json
db/seed/seed_retrieval_dictionaries.sql
tests/retrieval/doubles.py
tests/retrieval/test_sprint5.py
docs/sprint5/SPRINT5_REPORT.md
docs/sprint5/COMMIT_AND_TAG.md
VERSION
CHANGELOG.md
PROJECT_STATUS.md
```

## Suggested commands

```
git add -A
git commit -F docs/sprint5/COMMIT_AND_TAG.md   # (commit-message section)
git tag -a v0.6.0 -m "Sprint 5 — Retrieval (WF-002, canonical §452)"
```

## Tag

`v0.6.0` — Sprint 5 · Retrieval
```
Sprint 5 — Retrieval. WF-002 canonical §452 pipeline (SW-016…SW-021).
Valid Context Package produced and validated. 18/18 acceptance tests passing.
```
