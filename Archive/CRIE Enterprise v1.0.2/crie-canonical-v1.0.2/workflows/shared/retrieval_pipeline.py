"""
CRIE Retrieval — WF-002 pipeline orchestrator (canonical §452 ordering).

Order (§452, R-12; §63/§155 are summaries):
  Requirement Analysis → Metadata Expansion → Synonym Expansion →
  Acronym Normalization → Metadata Filtering → Keyword + Semantic Search →
  Candidate Merge → Deduplication → Authority Ranking → Cross-Encoder Rerank →
  Conflict Detection → Context Compression → Context Validation → Context Package

Non-bypass rule (§599/§608): the full pipeline executes in sequence; no
shortcuts. Empty-retrieval ladder per §471 (LLM SHALL NOT be called).

License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .adapters import (
    CrossEncoderAdapter,
    DictionaryStore,
    EmbeddingAdapter,
    RepositoryRetriever,
    RetrievalConfig,
)
from .analyze import (
    analyze_requirement,
    build_metadata_filters,
    select_strategy,
)
from .context import (
    build_context_package,
    compress,
    enforce_token_budget,
    validate_context_package,
)
from .rank import (
    apply_authority_and_freshness,
    composite_rank,
    deduplicate,
    detect_conflicts,
    hybrid_retrieve,
    rerank,
)


class _Timer:
    def __init__(self) -> None:
        self.timings: dict[str, float] = {}

    def stage(self, name: str, fn: Callable[[], Any]) -> Any:
        t0 = time.perf_counter()
        result = fn()
        self.timings[name] = round((time.perf_counter() - t0) * 1000.0, 3)
        return result


def run_retrieval(
    requirement: str,
    cfg: RetrievalConfig,
    dictionaries: DictionaryStore,
    retriever: RepositoryRetriever,
    embedder: EmbeddingAdapter,
    cross_encoder: CrossEncoderAdapter | None = None,
    metadata_hints: dict[str, Any] | None = None,
    repository_version: str = "",
) -> dict[str, Any]:
    """Execute WF-002 and return a validated Context Package (§294/§76).

    Raises ValueError if the produced package fails §74 validation
    (fail-fast, §298)."""
    timer = _Timer()

    # --- Requirement Analysis + Metadata/Synonym/Acronym expansion (§453-455)
    profile = timer.stage(
        "requirementAnalysis",
        lambda: analyze_requirement(requirement, cfg, dictionaries, metadata_hints),
    )
    strategy = select_strategy(profile, cfg)

    ladder = list(cfg.empty_retrieval.get("ladder", []))
    max_retries = int(cfg.empty_retrieval.get("maxRetries", 0))

    candidates: list[Any] = []
    retries = 0
    working_filters = timer.stage(
        "metadataFiltering",
        lambda: build_metadata_filters(profile, cfg),
    )
    working_profile = profile

    # --- Metadata Filtering → Keyword + Semantic → Merge, with §471 ladder ---
    while True:
        candidates = timer.stage(
            f"hybridRetrieve{'.retry' + str(retries) if retries else ''}",
            lambda: hybrid_retrieve(
                working_profile, strategy, working_filters, cfg, retriever, embedder
            ),
        )
        if candidates or retries >= max_retries:
            break
        # apply next ladder step (§471): retry → relax filters → expand synonyms
        step = ladder[retries] if retries < len(ladder) else "retry"
        if step == "relaxMetadataFilters":
            working_filters = {"repositoryStatus": "Certified"}
        elif step == "expandSynonyms":
            # broaden query with already-expanded terms if not already applied
            if working_profile.expanded_terms:
                working_profile.keywords = list(
                    dict.fromkeys(working_profile.keywords + working_profile.expanded_terms)
                )
        retries += 1

    candidate_count = len(candidates)

    if not candidates:
        # §471 exhausted → Insufficient Evidence. LLM SHALL NOT be called.
        package = build_context_package(
            requirement=requirement,
            profile=profile,
            candidates=[],
            conflicts=[],
            strategy=strategy,
            stats_extra={
                "candidateCount": 0,
                "afterDedup": 0,
                "reranked": False,
                "retries": retries,
                "stageTimingsMs": timer.timings,
            },
            cfg=cfg,
            repository_version=repository_version,
            insufficient_evidence=True,
        )
        _validate_or_raise(package)
        return package

    # --- Authority Ranking (§464/§439) + freshness (§463) + initial scoring ---
    timer.stage(
        "authorityRanking",
        lambda: apply_authority_and_freshness(candidates, cfg),
    )
    # --- Composite ranking (§462) ---
    timer.stage("compositeRanking", lambda: composite_rank(candidates, cfg))

    # --- Deduplication (§466) ---
    deduped = timer.stage("deduplication", lambda: deduplicate(candidates, cfg))

    # --- Cross-Encoder Rerank (§465) — gated (R-12/§305) ---
    reranked_result = timer.stage(
        "rerank", lambda: rerank(requirement, deduped, cfg, cross_encoder)
    )
    reranked_candidates, reranked_flag = reranked_result

    # --- Conflict Detection (§467) — preserved, never hidden ---
    conflicts = timer.stage(
        "conflictDetection", lambda: detect_conflicts(reranked_candidates)
    )

    # --- Context Compression (§468) + Token Budget (§469) ---
    compressed = timer.stage("compression", lambda: compress(reranked_candidates))
    budgeted, _tokens = timer.stage(
        "tokenBudget", lambda: enforce_token_budget(compressed, cfg)
    )

    # --- Emit + Context Validation (§294/§74) ---
    package = build_context_package(
        requirement=requirement,
        profile=profile,
        candidates=budgeted,
        conflicts=conflicts,
        strategy=strategy,
        stats_extra={
            "candidateCount": candidate_count,
            "afterDedup": len(deduped),
            "reranked": reranked_flag,
            "retries": retries,
            "stageTimingsMs": timer.timings,
        },
        cfg=cfg,
        repository_version=repository_version,
        insufficient_evidence=False,
    )
    _validate_or_raise(package)
    return package


def _validate_or_raise(package: dict[str, Any]) -> None:
    problems = validate_context_package(package)
    if problems:
        raise ValueError(
            "Context Package failed §74 validation: " + "; ".join(problems)
        )
