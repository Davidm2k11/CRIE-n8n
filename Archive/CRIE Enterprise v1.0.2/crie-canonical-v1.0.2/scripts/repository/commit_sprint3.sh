#!/usr/bin/env bash
# Sprint 3 commit + tag. Run from the CRIE repository root AFTER copying the
# Sprint 3 artifacts into their canonical paths (§634 naming, §619-635 tree).
# The build sandbox has no git repo/network, so this is executed in the real repo.
set -euo pipefail

# 1. Run the acceptance suite — must pass before committing (§607 Validation Gate).
node workflows/shared/../../tests/sprint3/acceptance.test.js 2>/dev/null || \
  node tests/sprint3/acceptance.test.js

# 2. Stage Sprint 3 deliverables.
git add \
  workflows/master/WF-001_Knowledge_Ingestion.json \
  workflows/master/WF-001_Knowledge_Ingestion.js \
  workflows/shared/module13_ingestion.js \
  prompts/knowledge_extraction/PR-001.yaml \
  prompts/metadata_extraction/PR-002.yaml \
  tests/sprint3/acceptance.test.js \
  tests/sprint3/fakes.js \
  examples/WF-001_example_input.json \
  examples/WF-001_example_output.json \
  docs/WF-001_Knowledge_Ingestion.md \
  docs/RELEASE_NOTES_v0.4.0.md \
  CHANGELOG.md VERSION PROJECT_STATUS.md

# 3. Commit (one sprint = coherent commit that leaves the project runnable, §606).
git commit -m "Sprint 3: Knowledge Ingestion (WF-001, SW-001..SW-015)

Implement WF-001 end-to-end via Module-13 sub-workflows SW-001..SW-015 (R-01):
deterministic pipeline correlation->SHA256->duplicate->register->OCR(retry x3)->
validate->metadata(PR-002)->knowledge(PR-001)->evidence->citation(R-06)->validate->
chunk->embed(1536,R-09)->repository writer(txn)->certification.

- Prompts loaded from registry, never embedded (§608).
- processing_history checkpoints at each stage (R-18).
- Failure policy: duplicate->stop, OCR->retry x3, extraction->human review,
  repository->rollback (§154).
- 17/17 acceptance+unit tests passing. Exit gate: one document -> CERTIFIED.

Targets v0.4.0."

# 4. Set VERSION and tag.
echo "0.4.0" > VERSION
git add VERSION
git commit --amend --no-edit
git tag -a v0.4.0 -m "Sprint 3 — Knowledge Ingestion"

echo "Committed and tagged v0.4.0."
