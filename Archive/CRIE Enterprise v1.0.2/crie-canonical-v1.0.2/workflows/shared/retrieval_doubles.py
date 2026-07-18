"""
In-memory adapter doubles for Sprint-5 retrieval tests.

These implement the real adapter Protocols and drive the REAL §452 pipeline
logic. No live datastore is required (accepted risk in PROJECT_STATUS.md);
live implementations are wired at the infrastructure-integration stage.

License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
"""

from __future__ import annotations

import hashlib
from typing import Any, Sequence

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from retrieval.adapters import Candidate  # noqa: E402


class FakeDictionaries:
    def __init__(self) -> None:
        self._syn = {
            "kpi": ["metric", "performance indicator"],
            "initiative": ["program", "strategic initiative"],
            "dashboard": ["reporting", "analytics", "visualization"],
        }
        self._acr = {
            "SRS": "software requirements specification",
            "KPI": "key performance indicator",
            "SLA": "service level agreement",
            "RBAC": "role based access control",
            "SSO": "single sign on",
        }
        self._meta = {
            "dashboard": ["reporting", "analytics", "visualization"],
            "risk": ["compliance", "audit"],
        }

    def synonyms(self, term: str) -> Sequence[str]:
        return self._syn.get(term, [])

    def acronym_expansion(self, acronym: str) -> str | None:
        return self._acr.get(acronym)

    def metadata_expansions(self, term: str) -> Sequence[str]:
        return self._meta.get(term, [])


def _det_embedding(text: str, dim: int = 1536) -> list[float]:
    """Deterministic pseudo-embedding for tests (unit-norm-ish)."""
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [((h[i % len(h)] / 255.0) - 0.5) for i in range(dim)]
    return vals


class FakeEmbedder:
    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        return _det_embedding(text, self.dim)


class FakeCrossEncoder:
    """Scores by keyword overlap; deterministic. Never retrieves (§465)."""

    def score(self, requirement: str, texts: Sequence[str]) -> list[float]:
        req_terms = set(requirement.lower().split())
        out = []
        for t in texts:
            terms = set(t.lower().split())
            overlap = len(req_terms & terms) / (len(req_terms) or 1)
            out.append(round(overlap, 6))
        return out


class FakeRepository:
    """Holds a corpus of Candidates; filters + scores in memory."""

    def __init__(self, corpus: list[Candidate]) -> None:
        self.corpus = corpus

    def _passes_filters(self, c: Candidate, filters: dict[str, Any]) -> bool:
        status = filters.get("repositoryStatus")
        if status and c.metadata.get("repositoryStatus") != status:
            return False
        product = filters.get("product")
        if product and c.metadata.get("product") != product:
            return False
        modules = filters.get("module")
        if modules:
            mods = modules if isinstance(modules, list) else [modules]
            if c.metadata.get("module") not in mods:
                return False
        return True

    def keyword_search(
        self, keywords: Sequence[str], filters: dict[str, Any], limit: int
    ) -> list[Candidate]:
        kw = set(k.lower() for k in keywords)
        results: list[Candidate] = []
        for c in self.corpus:
            if not self._passes_filters(c, filters):
                continue
            terms = set(c.text.lower().split())
            overlap = len(kw & terms)
            if overlap == 0:
                continue
            hit = _clone(c)
            hit.keyword_score = min(overlap / (len(kw) or 1), 1.0)
            hit.metadata_score = 1.0 if filters.get("product") == c.metadata.get("product") else 0.5
            results.append(hit)
        results.sort(key=lambda x: x.keyword_score, reverse=True)
        return results[:limit]

    def semantic_search(
        self,
        query_embedding: Sequence[float],
        filters: dict[str, Any],
        limit: int,
        minimum_similarity: float,
    ) -> list[Candidate]:
        results: list[Candidate] = []
        for c in self.corpus:
            if not self._passes_filters(c, filters):
                continue
            sim = _cosine(query_embedding, _det_embedding(c.text, len(query_embedding)))
            # rescale cosine (~ -1..1) into 0..1
            sim01 = (sim + 1.0) / 2.0
            if sim01 < minimum_similarity:
                continue
            hit = _clone(c)
            hit.semantic_score = round(sim01, 6)
            hit.metadata_score = 1.0 if filters.get("product") == c.metadata.get("product") else 0.5
            results.append(hit)
        results.sort(key=lambda x: x.semantic_score, reverse=True)
        return results[:limit]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _clone(c: Candidate) -> Candidate:
    from dataclasses import replace

    return replace(c, metadata=dict(c.metadata))
