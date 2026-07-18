"""
CRIE Retrieval — adapter interfaces and config loader.

Bridges the §452 retrieval pipeline to:
  - the Sprint-1 Provider Adapter layer (embeddings / cross-encoder),
  - the datastore (keyword + semantic retrieval, dictionaries, authority table),
  - the authored YAML configuration (R-08), loaded via the configuration cache.

No live datastore is required to exercise the real pipeline logic (accepted
risk in PROJECT_STATUS.md). In-memory doubles implement these Protocols for
tests; live implementations are wired at the infrastructure-integration stage.

License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
Unauthorized copying, modification, distribution, or commercial use is
prohibited without written permission.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover
    yaml = None


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RetrievalConfig:
    """Runtime view of retrieval.yaml + authority.yaml (R-08 authored source)."""

    top_k: int
    minimum_similarity: float
    metadata_filtering: bool
    authority_weight: float
    reranker_enabled: bool
    cross_encoder_model: str
    maximum_context_tokens: int
    default_strategy: str
    distance_metric: str
    embedding_dimension: int
    keyword: dict[str, Any]
    composite_weights: dict[str, float]
    freshness_enabled: bool
    freshness_half_life_days: int
    expansion: dict[str, bool]
    dedup_threshold: float
    empty_retrieval: dict[str, Any]
    context_quality: dict[str, Any]
    authority_sources: dict[str, int]
    authority_resolution: dict[str, str]

    def validate(self) -> None:
        """Fail-fast contract checks (§298)."""
        w = self.composite_weights
        total = round(sum(w.values()), 6)
        if total != 1.0:
            raise ValueError(
                f"§462 composite weights must sum to 1.00, got {total}: {w}"
            )
        if self.reranker_enabled and not self.cross_encoder_model:
            raise ValueError(
                "§305/§465 rerankerEnabled=true requires crossEncoderModel to be set."
            )
        if self.embedding_dimension != 1536:
            raise ValueError(
                "R-09 v1 lock-in: embeddingDimension must be 1536."
            )
        if not 0.0 <= self.minimum_similarity <= 1.0:
            raise ValueError("minimumSimilarity must be in [0,1].")
        if self.maximum_context_tokens <= 0:
            raise ValueError("§469 maximumContextTokens must be positive.")


def load_config(
    retrieval_yaml: str | Path,
    authority_yaml: str | Path,
) -> RetrievalConfig:
    """Load authored YAML (R-08) into the runtime RetrievalConfig view."""
    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML is required to load authored configuration.")
    r = yaml.safe_load(Path(retrieval_yaml).read_text(encoding="utf-8"))
    a = yaml.safe_load(Path(authority_yaml).read_text(encoding="utf-8"))

    authority_sources = {row["source"]: int(row["score"]) for row in a["authoritySources"]}

    cfg = RetrievalConfig(
        top_k=int(r["topK"]),
        minimum_similarity=float(r["minimumSimilarity"]),
        metadata_filtering=bool(r["metadataFiltering"]),
        authority_weight=float(r["authorityWeight"]),
        reranker_enabled=bool(r["rerankerEnabled"]),
        cross_encoder_model=str(r.get("crossEncoderModel", "") or ""),
        maximum_context_tokens=int(r["maximumContextTokens"]),
        default_strategy=str(r["defaultStrategy"]),
        distance_metric=str(r["distanceMetric"]),
        embedding_dimension=int(r["embeddingDimension"]),
        keyword=dict(r["keyword"]),
        composite_weights={k: float(v) for k, v in r["compositeWeights"].items()},
        freshness_enabled=bool(r["freshnessEnabled"]),
        freshness_half_life_days=int(r["freshnessHalfLifeDays"]),
        expansion={k: bool(v) for k, v in r["expansion"].items()},
        dedup_threshold=float(r["deduplication"]["semanticSimilarityThreshold"]),
        empty_retrieval=dict(r["emptyRetrieval"]),
        context_quality=dict(r["contextQuality"]),
        authority_sources=authority_sources,
        authority_resolution=dict(a["resolution"]),
    )
    cfg.validate()
    return cfg


# --------------------------------------------------------------------------- #
# Data shapes                                                                  #
# --------------------------------------------------------------------------- #
@dataclass
class Candidate:
    """A retrieval candidate. Scores remain independent (§461)."""

    knowledge_unit_id: str
    evidence_id: str
    citation_id: str | None
    text: str
    source_type: str                      # maps to authority.yaml source
    version: int
    updated_at: str                       # ISO-8601
    metadata: dict[str, Any] = field(default_factory=dict)
    # independent scores (§461)
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    metadata_score: float = 0.0
    authority_score: float = 0.0
    freshness_score: float = 0.0
    # derived
    composite_score: float = 0.0
    rerank_score: float | None = None
    token_estimate: int = 0
    claim_polarity: int = 0               # +1 supports / -1 negates / 0 neutral (§467)
    claim_key: str | None = None          # feature/claim identity for conflict pairing


# --------------------------------------------------------------------------- #
# Adapter Protocols (implemented by live infra OR in-memory test doubles)     #
# --------------------------------------------------------------------------- #
class DictionaryStore(Protocol):
    """Backed by configuration.synonyms / configuration.acronyms (0021)."""

    def synonyms(self, term: str) -> Sequence[str]: ...
    def acronym_expansion(self, acronym: str) -> str | None: ...
    def metadata_expansions(self, term: str) -> Sequence[str]: ...


class RepositoryRetriever(Protocol):
    """Backed by Supabase/pgvector + PostgreSQL FTS/trigram (§458/§459)."""

    def keyword_search(
        self, keywords: Sequence[str], filters: dict[str, Any], limit: int
    ) -> list[Candidate]: ...

    def semantic_search(
        self,
        query_embedding: Sequence[float],
        filters: dict[str, Any],
        limit: int,
        minimum_similarity: float,
    ) -> list[Candidate]: ...


class EmbeddingAdapter(Protocol):
    """Sprint-1 Provider Adapter layer — embedding provider."""

    def embed(self, text: str) -> list[float]: ...


class CrossEncoderAdapter(Protocol):
    """Sprint-1 Provider Adapter layer — cross-encoder (§465, gated)."""

    def score(self, requirement: str, texts: Sequence[str]) -> list[float]: ...
