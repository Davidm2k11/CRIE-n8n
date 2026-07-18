"""
CRIE Retrieval — SW-021 Context Builder.

  §468 context compression (deterministic; NEVER AI-summarize evidence).
  §469 token budget (lowest-ranked removed first).
  §470 context quality score (0.00..1.00).
  §74/§471 context validation + empty-retrieval handling.
  §294/§76 emit Context Package contract.

License: All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from .adapters import Candidate, RetrievalConfig
from .analyze import RequirementProfile


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate (~4 chars/token). Live impl uses tokenizer."""
    return max(1, (len(text) + 3) // 4)


# --------------------------------------------------------------------------- #
# §468 Context Compression (deterministic only)                               #
# --------------------------------------------------------------------------- #
def compress(candidates: list[Candidate]) -> list[Candidate]:
    """§468: remove duplicates / merge identical evidence / drop repeated
    citations, preserving authority and traceability. NEVER AI-summarize."""
    seen_text: set[str] = set()
    seen_cite: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:
        norm = " ".join(c.text.lower().split())
        if norm in seen_text:
            continue
        if c.citation_id and c.citation_id in seen_cite:
            # repeated citation on otherwise-distinct text: keep text, drop dup cite
            c = _copy_without_citation(c)
        seen_text.add(norm)
        if c.citation_id:
            seen_cite.add(c.citation_id)
        c.token_estimate = estimate_tokens(c.text)
        out.append(c)
    return out


def _copy_without_citation(c: Candidate) -> Candidate:
    from dataclasses import replace

    return replace(c, citation_id=None)


# --------------------------------------------------------------------------- #
# §469 Token Budget                                                            #
# --------------------------------------------------------------------------- #
def enforce_token_budget(
    candidates: list[Candidate], cfg: RetrievalConfig
) -> tuple[list[Candidate], int]:
    """§469: respect maximumContextTokens; lowest-ranked removed first."""
    ordered = _rank_order(candidates)
    kept: list[Candidate] = []
    total = 0
    for c in ordered:
        t = c.token_estimate or estimate_tokens(c.text)
        if total + t > cfg.maximum_context_tokens:
            continue  # lowest-ranked (later in order) dropped first
        kept.append(c)
        total += t
    return kept, total


def _rank_order(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Highest effective rank first: rerank_score if present else composite."""
    return sorted(
        candidates,
        key=lambda c: (c.rerank_score if c.rerank_score is not None else c.composite_score),
        reverse=True,
    )


# --------------------------------------------------------------------------- #
# §470 Context Quality Score                                                   #
# --------------------------------------------------------------------------- #
def quality_score(
    candidates: Sequence[Candidate],
    conflicts: Sequence[dict[str, Any]],
    cfg: RetrievalConfig,
) -> float:
    """§470: 0.00..1.00 from coverage, authority, citation completeness,
    knowledge diversity, conflict count, freshness."""
    if not candidates:
        return 0.0
    w = cfg.context_quality["weights"]
    n = len(candidates)

    coverage = min(n / max(cfg.top_k, 1), 1.0)
    authority = sum(c.authority_score for c in candidates) / n
    citation_completeness = sum(1 for c in candidates if c.citation_id) / n
    diversity = len({c.knowledge_unit_id for c in candidates}) / n
    freshness = sum(c.freshness_score for c in candidates) / n
    conflict_penalty = 1.0 / (1.0 + len(conflicts))

    score = (
        w["coverage"] * coverage
        + w["authority"] * authority
        + w["citationCompleteness"] * citation_completeness
        + w["knowledgeDiversity"] * diversity
        + w["conflictPenalty"] * conflict_penalty
        + w["freshness"] * freshness
    )
    return round(min(max(score, 0.0), 1.0), 4)


# --------------------------------------------------------------------------- #
# §261/§294/§76 Build Context Package + §74 validation                        #
# --------------------------------------------------------------------------- #
def build_context_package(
    requirement: str,
    profile: RequirementProfile,
    candidates: list[Candidate],
    conflicts: list[dict[str, Any]],
    strategy: str,
    stats_extra: dict[str, Any],
    cfg: RetrievalConfig,
    repository_version: str = "",
    insufficient_evidence: bool = False,
) -> dict[str, Any]:
    """Emit the Context Package contract (§294/§76). This is the ONLY object
    accepted by the Enterprise Reasoning Engine (§261)."""
    confidence = quality_score(candidates, conflicts, cfg)
    token_count = sum(c.token_estimate or estimate_tokens(c.text) for c in candidates)

    knowledge_units = _unique_by(
        [
            {"knowledgeUnitId": c.knowledge_unit_id, "sourceType": c.source_type,
             "authorityScore": c.authority_score, "version": c.version}
            for c in candidates
        ],
        key="knowledgeUnitId",
    )
    evidence = [
        {
            "evidenceId": c.evidence_id,
            "knowledgeUnitId": c.knowledge_unit_id,
            "text": c.text,
            "sourceType": c.source_type,
            "authorityScore": c.authority_score,
            "compositeScore": round(c.composite_score, 6),
            "rerankScore": (round(c.rerank_score, 6) if c.rerank_score is not None else None),
            "citationId": c.citation_id,
        }
        for c in candidates
    ]
    citations = _unique_by(
        [
            {"citationId": c.citation_id, "evidenceId": c.evidence_id,
             "knowledgeUnitId": c.knowledge_unit_id}
            for c in candidates
            if c.citation_id
        ],
        key="citationId",
    )

    package = {
        "schemaVersion": "1.1",
        "contextId": str(uuid.uuid4()),
        "requirement": requirement,
        "requirementProfile": profile.to_json(),
        "knowledgeUnits": knowledge_units,
        "evidence": evidence,
        "citations": citations,
        "conflicts": conflicts,
        "confidence": confidence,
        "statistics": {
            "strategy": strategy,
            "candidateCount": stats_extra.get("candidateCount", len(candidates)),
            "afterDedup": stats_extra.get("afterDedup", len(candidates)),
            "reranked": stats_extra.get("reranked", False),
            "conflictCount": len(conflicts),
            "tokenCount": token_count,
            "qualityScore": confidence,
            "emptyRetrieval": insufficient_evidence,
            "retries": stats_extra.get("retries", 0),
            "stageTimingsMs": stats_extra.get("stageTimingsMs", {}),
        },
        "insufficientEvidence": insufficient_evidence,
        "repositoryVersion": repository_version,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    return package


def _unique_by(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[Any] = set()
    out: list[dict[str, Any]] = []
    for r in rows:
        v = r.get(key)
        if v in seen:
            continue
        seen.add(v)
        out.append(r)
    return out


# --------------------------------------------------------------------------- #
# §74 Context Validation                                                       #
# --------------------------------------------------------------------------- #
REQUIRED_FIELDS = (
    "schemaVersion", "contextId", "requirement", "requirementProfile",
    "knowledgeUnits", "evidence", "citations", "conflicts", "confidence",
    "statistics", "createdAt",
)


def validate_context_package(package: dict[str, Any]) -> list[str]:
    """§74/§298 fail-fast validation. Returns a list of problems (empty = valid)."""
    problems: list[str] = []
    for f in REQUIRED_FIELDS:
        if f not in package:
            problems.append(f"missing required field: {f}")
    if package.get("schemaVersion") != "1.1":
        problems.append("schemaVersion must be '1.1' (§296)")
    conf = package.get("confidence")
    if not isinstance(conf, (int, float)) or not 0.0 <= float(conf) <= 1.0:
        problems.append("confidence must be a number in [0,1] (§470)")

    # An empty package is only valid when explicitly flagged insufficient (§471).
    if not package.get("evidence"):
        if not package.get("insufficientEvidence"):
            problems.append(
                "empty evidence without insufficientEvidence flag (§74/§471)"
            )
    else:
        # every evidence item must be traceable to a knowledge unit (§468 traceability)
        ku_ids = {k["knowledgeUnitId"] for k in package.get("knowledgeUnits", [])}
        for ev in package["evidence"]:
            if ev.get("knowledgeUnitId") not in ku_ids:
                problems.append(
                    f"evidence {ev.get('evidenceId')} not traceable to a knowledge unit"
                )
                break
    return problems
