"""
CRIE Sprint 5 — Retrieval acceptance tests (WF-002, §452).

Each test maps to a backlog task (S5-1 .. S5-15) and/or an exit-gate criterion.
Runs the REAL pipeline against in-memory adapter doubles (accepted risk).

Run: python -m pytest tests/retrieval/test_sprint5.py -v
  or: python tests/retrieval/test_sprint5.py   (built-in runner, no pytest)

License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Canonical path bootstrap: reconstructs the `retrieval` package and `doubles`
# module from the flattened workflows/shared/*.py canonical sources.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _pathsetup  # noqa: E402,F401

from retrieval import (  # noqa: E402
    analyze_requirement,
    build_metadata_filters,
    load_config,
    run_retrieval,
    select_strategy,
    validate_context_package,
)
from retrieval.adapters import Candidate  # noqa: E402
from retrieval.rank import (  # noqa: E402
    apply_authority_and_freshness,
    composite_rank,
    deduplicate,
    detect_conflicts,
    rerank,
)
from doubles import (  # noqa: E402
    FakeCrossEncoder,
    FakeDictionaries,
    FakeEmbedder,
    FakeRepository,
)

CFG_DIR = ROOT / "configuration"


def _cfg(**overrides):
    cfg = load_config(CFG_DIR / "retrieval.yaml", CFG_DIR / "authority.yaml")
    if overrides:
        from dataclasses import replace

        cfg = replace(cfg, **overrides)
        cfg.validate()
    return cfg


def _corpus() -> list[Candidate]:
    base = dict(repositoryStatus="Certified", product="Acme")
    return [
        Candidate(
            knowledge_unit_id="KU1", evidence_id="EV1", citation_id="C1",
            text="the dashboard supports reporting and analytics for kpi metric tracking",
            source_type="Approved Product Specification", version=3,
            updated_at="2026-05-01T00:00:00Z",
            metadata={**base, "module": "Reporting"},
            claim_key="dashboard-reporting", claim_polarity=1,
        ),
        Candidate(
            knowledge_unit_id="KU2", evidence_id="EV2", citation_id="C2",
            text="training material notes the dashboard does not support reporting export",
            source_type="Training Material", version=1,
            updated_at="2025-01-01T00:00:00Z",
            metadata={**base, "module": "Reporting"},
            claim_key="dashboard-reporting", claim_polarity=-1,
        ),
        Candidate(
            knowledge_unit_id="KU3", evidence_id="EV3", citation_id="C3",
            text="role based access control sso single sign on is configurable per tenant",
            source_type="Product Manual", version=2,
            updated_at="2026-06-01T00:00:00Z",
            metadata={**base, "module": "Security"},
        ),
        Candidate(
            knowledge_unit_id="KU1", evidence_id="EV1b", citation_id="C1",
            text="the dashboard supports reporting and analytics for kpi metric tracking",
            source_type="Approved Product Specification", version=3,
            updated_at="2026-05-01T00:00:00Z",
            metadata={**base, "module": "Reporting"},
        ),  # near-duplicate of EV1 (§466)
    ]


def _deps():
    return dict(
        dictionaries=FakeDictionaries(),
        retriever=FakeRepository(_corpus()),
        embedder=FakeEmbedder(),
    )


# --------------------------------------------------------------------------- #
# S5-1 / SW-016 requirement analyzer + normalization                          #
# --------------------------------------------------------------------------- #
def test_s5_1_requirement_analyzer_normalization():
    cfg = _cfg()
    prof = analyze_requirement(
        "Does the Dashboard support KPI reporting?", cfg, FakeDictionaries()
    )
    assert prof.normalized_query == prof.normalized_query.lower()
    assert "?" not in prof.normalized_query
    assert "the" not in prof.keywords  # stopword removed
    assert prof.language == "en"


# --------------------------------------------------------------------------- #
# S5-2 metadata + synonym/acronym expansion                                   #
# --------------------------------------------------------------------------- #
def test_s5_2_synonym_and_acronym_expansion():
    cfg = _cfg()
    prof = analyze_requirement("Show KPI on the SRS dashboard", cfg, FakeDictionaries())
    # acronym SRS → software requirements specification
    assert "software" in prof.keywords
    # synonym kpi → metric / performance indicator
    assert "metric" in prof.keywords
    # metadata expansion of dashboard present in filters
    assert "expandedTopics" in prof.filters


def test_s5_2_expansion_respects_toggles():
    cfg = _cfg(expansion={"metadataExpansion": False,
                          "synonymExpansion": False,
                          "acronymNormalization": False})
    prof = analyze_requirement("Show KPI on the SRS dashboard", cfg, FakeDictionaries())
    assert "metric" not in prof.keywords
    assert "software" not in prof.keywords


# --------------------------------------------------------------------------- #
# S5-3 retrieval strategy selection                                           #
# --------------------------------------------------------------------------- #
def test_s5_3_strategy_selection_defaults_hybrid():
    cfg = _cfg()
    prof = analyze_requirement("dashboard reporting", cfg, FakeDictionaries())
    assert select_strategy(prof, cfg) == "Hybrid"


# --------------------------------------------------------------------------- #
# S5-4 / SW-017 metadata filter                                               #
# --------------------------------------------------------------------------- #
def test_s5_4_metadata_filter_certified_only():
    cfg = _cfg()
    prof = analyze_requirement("dashboard", cfg, FakeDictionaries(),
                               metadata_hints={"product": "Acme", "modules": ["Reporting"]})
    filters = build_metadata_filters(prof, cfg)
    assert filters["repositoryStatus"] == "Certified"
    assert filters["product"] == "Acme"


# --------------------------------------------------------------------------- #
# S5-5 / S5-6 keyword + hybrid retrieval                                      #
# --------------------------------------------------------------------------- #
def test_s5_6_hybrid_retrieval_returns_candidates():
    cfg = _cfg()
    pkg = run_retrieval("dashboard reporting analytics", cfg, **_deps())
    assert pkg["statistics"]["strategy"] == "Hybrid"
    assert pkg["statistics"]["candidateCount"] >= 1
    assert len(pkg["evidence"]) >= 1


# --------------------------------------------------------------------------- #
# S5-7 / S5-8 candidate merge + composite ranking                            #
# --------------------------------------------------------------------------- #
def test_s5_8_composite_ranking_orders_by_score():
    cfg = _cfg()
    cands = _corpus()[:3]
    apply_authority_and_freshness(cands, cfg)
    for c in cands:
        c.semantic_score = 0.8
        c.keyword_score = 0.5
    composite_rank(cands, cfg)
    # Approved Product Spec (authority 1.0) should outrank Training Material
    spec = next(c for c in cands if c.source_type == "Approved Product Specification")
    train = next(c for c in cands if c.source_type == "Training Material")
    assert spec.composite_score > train.composite_score


# --------------------------------------------------------------------------- #
# S5-9 / SW-019 rerank gate (R-12/§305)                                        #
# --------------------------------------------------------------------------- #
def test_s5_9_rerank_disabled_by_default():
    cfg = _cfg()
    cands = _corpus()[:3]
    out, flag = rerank("dashboard reporting", cands, cfg, FakeCrossEncoder())
    assert flag is False  # gated off


def test_s5_9_rerank_enabled_with_model():
    cfg = _cfg(reranker_enabled=True, cross_encoder_model="test-cross-encoder")
    cands = _corpus()[:3]
    out, flag = rerank("dashboard reporting", cands, cfg, FakeCrossEncoder())
    assert flag is True
    assert all(c.rerank_score is not None for c in out[: len(cands)])


def test_s5_9_config_rejects_enabled_without_model():
    try:
        _cfg(reranker_enabled=True, cross_encoder_model="")
        raised = False
    except ValueError:
        raised = True
    assert raised


# --------------------------------------------------------------------------- #
# S5-10 duplicate removal (§466)                                              #
# --------------------------------------------------------------------------- #
def test_s5_10_duplicate_removal():
    cfg = _cfg()
    cands = _corpus()  # EV1 and EV1b are near-duplicates
    apply_authority_and_freshness(cands, cfg)
    composite_rank(cands, cfg)
    kept = deduplicate(cands, cfg)
    texts = [c.evidence_id for c in kept]
    # only one of the identical-text EV1/EV1b survives
    assert not ("EV1" in texts and "EV1b" in texts)


# --------------------------------------------------------------------------- #
# S5-11 / SW-020 conflict detection (§467)                                    #
# --------------------------------------------------------------------------- #
def test_s5_11_conflict_detection_preserved():
    cfg = _cfg()
    cands = _corpus()[:2]  # supporting + contradicting on same claim
    apply_authority_and_freshness(cands, cfg)
    conflicts = detect_conflicts(cands)
    assert len(conflicts) == 1
    assert conflicts[0]["claimKey"] == "dashboard-reporting"
    assert conflicts[0]["supporting"] and conflicts[0]["contradicting"]


# --------------------------------------------------------------------------- #
# S5-12 authority scoring — 9 sources (R-16)                                  #
# --------------------------------------------------------------------------- #
def test_s5_12_authority_nine_source_model():
    cfg = _cfg()
    assert len(cfg.authority_sources) == 9
    assert cfg.authority_sources["Approved Product Specification"] == 100
    assert cfg.authority_sources["Internal Notes"] == 40


def test_s5_12_freshness_never_overrides_authority():
    cfg = _cfg()
    # old authoritative vs new low-authority
    old_spec = Candidate("KUa", "EVa", "Ca", "same text tokens here",
                         "Approved Product Specification", 1, "2020-01-01T00:00:00Z", {})
    new_notes = Candidate("KUb", "EVb", "Cb", "same text tokens here",
                          "Internal Notes", 5, "2026-07-01T00:00:00Z", {})
    both = [old_spec, new_notes]
    for c in both:
        c.semantic_score = 0.5
        c.keyword_score = 0.5
    apply_authority_and_freshness(both, cfg)
    composite_rank(both, cfg)
    assert old_spec.composite_score > new_notes.composite_score


# --------------------------------------------------------------------------- #
# S5-13 / SW-021 context builder + compression + token budget                 #
# --------------------------------------------------------------------------- #
def test_s5_13_token_budget_enforced():
    cfg = _cfg(maximum_context_tokens=20)  # tiny budget forces trimming
    pkg = run_retrieval("dashboard reporting analytics kpi", cfg, **_deps())
    assert pkg["statistics"]["tokenCount"] <= 20


# --------------------------------------------------------------------------- #
# S5-14 context validation + empty-retrieval strategy (§74/§471)              #
# --------------------------------------------------------------------------- #
def test_s5_14_empty_retrieval_insufficient_evidence():
    cfg = _cfg()
    empty_repo = FakeRepository([])
    pkg = run_retrieval("nonexistent quantum flux capacitor", cfg,
                        dictionaries=FakeDictionaries(),
                        retriever=empty_repo, embedder=FakeEmbedder())
    assert pkg["insufficientEvidence"] is True
    assert pkg["evidence"] == []
    assert validate_context_package(pkg) == []  # still a valid package


# --------------------------------------------------------------------------- #
# S5-15 emit + validate Context Package contract (§294/§76) — EXIT GATE       #
# --------------------------------------------------------------------------- #
def test_s5_15_context_package_valid_exit_gate():
    cfg = _cfg()
    pkg = run_retrieval("dashboard reporting analytics", cfg, **_deps())
    problems = validate_context_package(pkg)
    assert problems == [], f"validation problems: {problems}"
    assert pkg["schemaVersion"] == "1.1"
    assert 0.0 <= pkg["confidence"] <= 1.0
    # every evidence traces to a knowledge unit (§468 traceability)
    ku = {k["knowledgeUnitId"] for k in pkg["knowledgeUnits"]}
    assert all(e["knowledgeUnitId"] in ku for e in pkg["evidence"])


def test_non_bypass_full_pipeline_telemetry():
    # §599/§608 non-bypass: each stage emits telemetry.
    cfg = _cfg()
    pkg = run_retrieval("dashboard reporting analytics", cfg, **_deps())
    timings = pkg["statistics"]["stageTimingsMs"]
    for stage in ("requirementAnalysis", "metadataFiltering", "authorityRanking",
                  "compositeRanking", "deduplication", "rerank",
                  "conflictDetection", "compression", "tokenBudget"):
        assert stage in timings


# --------------------------------------------------------------------------- #
# Built-in runner (no pytest dependency)                                       #
# --------------------------------------------------------------------------- #
def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_run_all())
