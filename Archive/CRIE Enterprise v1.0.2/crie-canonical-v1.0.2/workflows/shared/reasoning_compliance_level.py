# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
"""
Deterministic complianceLevel derivation.

Governance: R-11 (spec §480/§481, §478-479, §84).
The LLM (SW-023) produces ONLY the explanation + evidence-to-requirement
mapping. `complianceLevel` is derived here, deterministically, by applying:
  1. Evidence-sufficiency gate (§481): >=1 KnowledgeUnit AND >=1 Evidence
     AND >=1 Citation. Missing any -> "Insufficient Evidence".
  2. Decision matrix (§480), keyed on the evidence-mapping SIGNAL produced
     by the model, never on a level the model asserts.

The model's own suggested level, if present, is advisory input only (R-11),
exactly as its confidence is advisory (R-10).
"""
from __future__ import annotations

from enum import Enum
from typing import Optional


class ComplianceLevel(str, Enum):
    """Canonical compliance levels (§84). Value strings are the contract wire form."""

    FULLY_COMPLIANT = "Fully Compliant"
    PARTIALLY_COMPLIANT = "Partially Compliant"
    CONFIGURABLE = "Configurable"
    CUSTOM_DEVELOPMENT_REQUIRED = "Custom Development Required"
    NOT_SUPPORTED = "Not Supported"
    INSUFFICIENT_EVIDENCE = "Insufficient Evidence"


# §480 Compliance Decision Matrix — deterministic map from the evidence SIGNAL
# (derived from the model's evidence mapping, not from any model-asserted level)
# to the resulting level. This table SHALL remain deterministic (§480).
DECISION_MATRIX = {
    "strong_supporting": ComplianceLevel.FULLY_COMPLIANT,
    "partial": ComplianceLevel.PARTIALLY_COMPLIANT,
    "configuration_available": ComplianceLevel.CONFIGURABLE,
    "requires_customization": ComplianceLevel.CUSTOM_DEVELOPMENT_REQUIRED,
    "strong_contradictory": ComplianceLevel.NOT_SUPPORTED,
    "missing": ComplianceLevel.INSUFFICIENT_EVIDENCE,
}

VALID_SIGNALS = frozenset(DECISION_MATRIX.keys())


def evidence_sufficient(
    knowledge_unit_count: int, evidence_count: int, citation_count: int
) -> bool:
    """§481 evidence-sufficiency gate. All three components required."""
    return knowledge_unit_count >= 1 and evidence_count >= 1 and citation_count >= 1


def derive_compliance_level(
    *,
    knowledge_unit_count: int,
    evidence_count: int,
    citation_count: int,
    evidence_signal: str,
) -> ComplianceLevel:
    """
    Derive complianceLevel deterministically (R-11).

    Order of operations:
      1. §481 sufficiency gate first. If unmet -> Insufficient Evidence,
         regardless of any model-emitted signal.
      2. Otherwise apply the §480 matrix to the evidence signal.

    `evidence_signal` is the platform's classification of the model's evidence
    mapping into one of VALID_SIGNALS. An unknown signal is treated as "missing"
    (fail safe -> Insufficient Evidence), never guessed.
    """
    if not evidence_sufficient(knowledge_unit_count, evidence_count, citation_count):
        return ComplianceLevel.INSUFFICIENT_EVIDENCE

    signal = (evidence_signal or "").strip().lower()
    if signal not in VALID_SIGNALS:
        return ComplianceLevel.INSUFFICIENT_EVIDENCE
    return DECISION_MATRIX[signal]


def requires_review_by_level(level: ComplianceLevel) -> bool:
    """§491/§91: these levels always force human review."""
    return level in (
        ComplianceLevel.CUSTOM_DEVELOPMENT_REQUIRED,
        ComplianceLevel.INSUFFICIENT_EVIDENCE,
    )
