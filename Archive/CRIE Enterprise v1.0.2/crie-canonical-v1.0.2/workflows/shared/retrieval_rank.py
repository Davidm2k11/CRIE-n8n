"""
CRIE Retrieval — hybrid retrieval, scoring, ranking, dedup, rerank, conflicts.

  SW-018 (§258, §459/§458): hybrid semantic + keyword retrieval, candidate merge.
  §461 initial scoring, §462 composite ranking, §463 freshness, §464 authority.
  §466 duplicate detection.
  SW-019 (§259, §465): cross-encoder rerank — GATED by rerankerEnabled (R-12/§305).
  SW-020 (§260, §467): conflict detection — conflicts preserved, never hidden.

License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Sequence

from .adapters import (
    Candidate,
    CrossEncoderAdapter,
    EmbeddingAdapter,
    RepositoryRetriever,
    RetrievalConfig,
)
from .analyze import RequirementProfile


# --------------------------------------------------------------------------- #
# SW-018 Hybrid Retriever (§258, §458 keyword + §459 semantic + §460 merge)   #
# --------------------------------------------------------------------------- #
def hybrid_retrieve(
    profile: RequirementProfile,
    strategy: str,
    filters: dict[str, Any],
    cfg: RetrievalConfig,
    retriever: RepositoryRetriever,
    embedder: EmbeddingAdapter,
) -> list[Candidate]:
    """Execute strategy-selected retrieval and merge (§456/§458/§459/§460)."""
    keyword_hits: list[Candidate] = []
    semantic_hits: list[Candidate] = []

    if strategy in ("KeywordOnly", "Hybrid", "MetadataOnly"):
        keyword_hits = retriever.keyword_search(
            profile.keywords, filters, cfg.top_k
        )
    if strategy in ("SemanticOnly", "Hybrid"):
        query_embedding = embedder.embed(profile.normalized_query)
        if len(query_embedding) != cfg.embedding_dimension:
            raise ValueError(
                f"R-09 dimension mismatch: expected {cfg.embedding_dimension}, "
                f"got {len(query_embedding)}."
            )
        semantic_hits = retriever.semantic_search(
            query_embedding, filters, cfg.top_k, cfg.minimum_similarity
        )

    return merge_candidates(keyword_hits, semantic_hits)


def merge_candidates(
    keyword_hits: list[Candidate], semantic_hits: list[Candidate]
) -> list[Candidate]:
    """§460 candidate merge. Duplicate candidates merge scores; scores stay
    independent (§461)."""
    merged: dict[str, Candidate] = {}
    for c in keyword_hits + semantic_hits:
        existing = merged.get(c.evidence_id)
        if existing is None:
            merged[c.evidence_id] = c
        else:
            # merge independent scores by taking max of each dimension (§460/§461)
            existing.keyword_score = max(existing.keyword_score, c.keyword_score)
            existing.semantic_score = max(existing.semantic_score, c.semantic_score)
            existing.metadata_score = max(existing.metadata_score, c.metadata_score)
    return list(merged.values())


# --------------------------------------------------------------------------- #
# §464 Authority ranking & §463 freshness                                     #
# --------------------------------------------------------------------------- #
def apply_authority_and_freshness(
    candidates: Sequence[Candidate], cfg: RetrievalConfig
) -> None:
    """Assign authority_score (§439/§464) and freshness_score (§463) in place."""
    max_auth = max(cfg.authority_sources.values()) or 1
    now = datetime.now(timezone.utc)
    hl = max(cfg.freshness_half_life_days, 1)
    for c in candidates:
        raw_auth = cfg.authority_sources.get(c.source_type, 0)
        c.authority_score = raw_auth / max_auth  # normalise 0..1
        if cfg.freshness_enabled:
            age_days = _age_days(c.updated_at, now)
            c.freshness_score = math.pow(0.5, age_days / hl)  # exponential decay
        else:
            c.freshness_score = 0.0


def _age_days(iso_ts: str, now: datetime) -> float:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.0
    return max((now - dt).total_seconds() / 86400.0, 0.0)


# --------------------------------------------------------------------------- #
# §462 Composite ranking formula (weights configurable)                       #
# --------------------------------------------------------------------------- #
def composite_rank(candidates: Sequence[Candidate], cfg: RetrievalConfig) -> None:
    """Assign composite_score in place per §462 weights."""
    w = cfg.composite_weights
    for c in candidates:
        c.composite_score = (
            w["semanticSimilarity"] * c.semantic_score
            + w["authority"] * c.authority_score
            + w["keywordScore"] * c.keyword_score
            + w["metadataMatch"] * c.metadata_score
            + w["documentFreshness"] * c.freshness_score
        )


# --------------------------------------------------------------------------- #
# §466 Duplicate detection                                                    #
# --------------------------------------------------------------------------- #
def deduplicate(
    candidates: list[Candidate], cfg: RetrievalConfig
) -> list[Candidate]:
    """§466: merge duplicates; keep only the highest-ranked candidate.

    Duplicate criteria: same Knowledge Unit, same Evidence, same Citation, or
    high semantic similarity (approximated here by identical normalized text at
    or above the configured similarity threshold via exact-text grouping; live
    impl uses embedding similarity)."""
    ranked = sorted(candidates, key=lambda c: c.composite_score, reverse=True)
    kept: list[Candidate] = []
    seen_ku: set[str] = set()
    seen_ev: set[str] = set()
    seen_cite: set[str] = set()
    seen_text: set[str] = set()
    for c in ranked:
        norm_text = " ".join(c.text.lower().split())
        if (
            c.evidence_id in seen_ev
            or (c.citation_id and c.citation_id in seen_cite)
            or norm_text in seen_text
        ):
            continue
        # Same-KU near-duplicate: keep only first (highest-ranked) per KU when
        # text overlap is high.
        if c.knowledge_unit_id in seen_ku and norm_text in seen_text:
            continue
        kept.append(c)
        seen_ku.add(c.knowledge_unit_id)
        seen_ev.add(c.evidence_id)
        if c.citation_id:
            seen_cite.add(c.citation_id)
        seen_text.add(norm_text)
    return kept


# --------------------------------------------------------------------------- #
# SW-019 Cross-Encoder Reranker (§259/§465) — GATED (R-12/§305)               #
# --------------------------------------------------------------------------- #
def rerank(
    requirement: str,
    candidates: list[Candidate],
    cfg: RetrievalConfig,
    cross_encoder: CrossEncoderAdapter | None,
) -> tuple[list[Candidate], bool]:
    """§465: improve final ordering. Returns (candidates, reranked_flag).

    GATE: only runs when rerankerEnabled and a model + adapter are present
    (R-12/§305). Cross-encoder SHALL NOT retrieve new information (§465)."""
    if not cfg.reranker_enabled:
        return candidates, False
    if not cfg.cross_encoder_model or cross_encoder is None:
        # Config invariant already checked in cfg.validate(); defensive here.
        return candidates, False

    top_n = candidates[: cfg.top_k]
    scores = cross_encoder.score(requirement, [c.text for c in top_n])
    for c, s in zip(top_n, scores):
        c.rerank_score = float(s)
    reranked = sorted(
        top_n, key=lambda c: (c.rerank_score if c.rerank_score is not None else -1.0),
        reverse=True,
    )
    # candidates beyond top_n keep composite order after the reranked head
    tail = candidates[cfg.top_k:]
    return reranked + tail, True


# --------------------------------------------------------------------------- #
# SW-020 Conflict Detector (§260/§467) — conflicts preserved, never hidden    #
# --------------------------------------------------------------------------- #
def detect_conflicts(candidates: Sequence[Candidate]) -> list[dict[str, Any]]:
    """§467: detect contradictory evidence (Supports vs Does Not Support).

    Conflicts SHALL be preserved (§467); resolution presentation is the
    Reasoning Engine's responsibility, not retrieval's."""
    conflicts: list[dict[str, Any]] = []
    by_claim: dict[str, list[Candidate]] = {}
    for c in candidates:
        if c.claim_key and c.claim_polarity != 0:
            by_claim.setdefault(c.claim_key, []).append(c)

    for claim_key, group in by_claim.items():
        polarities = {c.claim_polarity for c in group}
        if 1 in polarities and -1 in polarities:
            conflicts.append(
                {
                    "claimKey": claim_key,
                    "supporting": [
                        {
                            "evidenceId": c.evidence_id,
                            "knowledgeUnitId": c.knowledge_unit_id,
                            "authorityScore": c.authority_score,
                        }
                        for c in group
                        if c.claim_polarity == 1
                    ],
                    "contradicting": [
                        {
                            "evidenceId": c.evidence_id,
                            "knowledgeUnitId": c.knowledge_unit_id,
                            "authorityScore": c.authority_score,
                        }
                        for c in group
                        if c.claim_polarity == -1
                    ],
                    "resolution": "deferToReasoning",  # §467/§440
                }
            )
    return conflicts
