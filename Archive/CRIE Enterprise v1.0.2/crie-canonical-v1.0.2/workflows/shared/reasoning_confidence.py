# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
"""
Platform-computed confidence engine.

Governance: R-10 (spec §89, §483, §484).
The platform computes the authoritative `confidence`; the LLM SHALL NOT produce
it. Any value the model emits is captured only as `modelSelfConfidence` and is
advisory input, never authoritative.

§483 factors combined here:
  - Retrieval Confidence
  - Evidence Quality
  - Authority
  - Citation Coverage
  - Consistency (conflict detection reduces confidence, §482)

Weights are configurable (§484 "Thresholds SHALL remain configurable"); defaults
below are authored in config/reasoning.config.yaml as the source of truth (R-08)
and passed in. No value is hardcoded into a workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ConfidenceWeights:
    """Configurable §483 factor weights. Loaded from reasoning.config.yaml."""

    retrieval_confidence: float
    evidence_quality: float
    authority: float
    citation_coverage: float
    consistency: float

    def total(self) -> float:
        return (
            self.retrieval_confidence
            + self.evidence_quality
            + self.authority
            + self.citation_coverage
            + self.consistency
        )


@dataclass(frozen=True)
class ConfidenceInputs:
    """
    Normalized [0,1] platform-measured signals feeding the §483 model.

    None of these is the model's self-confidence. `model_self_confidence` is
    carried separately for audit and is NEVER used in this computation (R-10).
    """

    retrieval_confidence: float  # from Context Package (§75), already [0,1]
    evidence_quality: float  # mean evidence.confidence over supporting evidence
    authority: float  # normalized authority score of supporting KUs (§439, /100)
    citation_coverage: float  # fraction of conclusions with >=1 citation (§88)
    consistency: float  # 1.0 minus conflict penalty (§482)


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def compute_confidence(inputs: ConfidenceInputs, weights: ConfidenceWeights) -> float:
    """
    Weighted, normalized combination of the §483 factors, returning [0.00, 1.00].

    Deterministic and reproducible (§113). Rounded to 2 decimals to match the
    §89 / §484 scale.
    """
    denom = weights.total()
    if denom <= 0:
        raise ValueError("ConfidenceWeights must sum to a positive value")

    score = (
        weights.retrieval_confidence * _clamp01(inputs.retrieval_confidence)
        + weights.evidence_quality * _clamp01(inputs.evidence_quality)
        + weights.authority * _clamp01(inputs.authority)
        + weights.citation_coverage * _clamp01(inputs.citation_coverage)
        + weights.consistency * _clamp01(inputs.consistency)
    ) / denom

    return round(_clamp01(score), 2)


# §484 Confidence Interpretation bands (informational; not part of the contract).
def interpret_confidence(score: float) -> str:
    if score >= 0.95:
        return "Extremely High"
    if score >= 0.90:
        return "Very High"
    if score >= 0.80:
        return "High"
    if score >= 0.65:
        return "Medium"
    if score >= 0.50:
        return "Low"
    return "Human Review Required"
