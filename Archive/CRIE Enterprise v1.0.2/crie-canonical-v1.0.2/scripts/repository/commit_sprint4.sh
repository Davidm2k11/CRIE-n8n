#!/usr/bin/env bash
# Sprint 4 commit + tag. Run from the CRIE repository root AFTER integrating the
# Sprint 4 artifacts into their canonical paths (§634 naming, §619-635 tree).
# Adjust paths to match the canonical repository layout.
set -euo pipefail

# 1. Validation Gate (§607): Sprint 4 tests must pass before committing.
node tests/sprint4/acceptance.test.js

# 2. Stage Sprint 4 deliverables.
git add \
  repository/certification.js \
  repository/writer.js \
  repository/health_statistics.js \
  repository/api.js \
  tests/sprint4/acceptance.test.js \
  tests/sprint4/fakes.js \
  examples/repository_api_example_input.json \
  examples/repository_api_example_output.json \
  docs/Repository.md \
  docs/RELEASE_NOTES_v0.5.0.md \
  CHANGELOG.md VERSION PROJECT_STATUS.md

# 3. Commit (one sprint = coherent commit that leaves the project runnable, §606).
git commit -m "Sprint 4: Repository (certification, versioning, APIs, health, statistics)

Persist certified knowledge on the Sprint 2 schema, consuming the Sprint 3
ingestion bundle:
- Hardened transactional Repository Writer with §524/§525/§427 integrity +
  governance gates; rollback on failure (§148/§234).
- Certification framework: per-KU (§512) + per-document (§428/§527); quality
  score (§511); §527 certification object.
- Versioning + lineage (§519/§522): previous_version/created_by/change_reason,
  lifecycle states (§518); deprecate-not-delete.
- Repository API (§365/§56): create/update/archive, certified-only reads,
  rebuild embeddings (reserved, §523; 1536 enforced R-09), statistics, health.
- Repository Health (§528) + Statistics (§529).
- Ownership enforcement (R-13/§425): chunks/embeddings owned by Repository;
  Compliance Result/Context Package/prompts refused (§427/§54).

21/21 acceptance+unit tests passing. Exit gate: repository operational,
certification passes, APIs/health/statistics available, Repository never bypassed.

Targets v0.5.0."

# 4. Tag.
git tag -a v0.5.0 -m "Sprint 4 — Repository"

echo "Committed and tagged v0.5.0."
