# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
"""
SW-024 — Output Validator, plus hallucination detection, self-validation, and
the human-review decision.

Governance:
  - §264 SW-024 checks (JSON valid, required fields, citations, confidence,
    compliance level) + retry on failure.
  - §90 Output Validation / §298 contract validation (fail fast).
  - §493 Hallucination Detection (every statement references evidence; every
    citation exists; every capability exists in repository).
  - §494 Self Validation ordered gate.
  - §491 / §91 Human Review Decision.
  - PR-005 Output Validation prompt is loaded via SW-022 for the LLM-assisted
    check (§181), but validation SHALL NOT modify the response (§181); the
    deterministic checks below are authoritative for pass/fail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .compliance_level import ComplianceLevel, requires_review_by_level

# §295 required (non-empty) fields for a valid Compliance Result.
REQUIRED_FIELDS = (
    "schemaVersion",
    "requirementId",
    "requirement",
    "decision",
    "complianceLevel",
    "confidence",
    "explanation",
    "generatedAt",
)

_VALID_LEVELS = {lvl.value for lvl in ComplianceLevel}


@dataclass
class ValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # allow `if result:`
        return self.valid


def validate_output(result: dict) -> ValidationResult:
    """
    SW-024 deterministic validation (§264/§90/§298).

    Checks: JSON structure (dict), required fields present + non-empty,
    complianceLevel in the §84 enum, confidence a number in [0,1], citations
    attached (unless level is Insufficient Evidence, where absence is expected).
    """
    errors: List[str] = []

    if not isinstance(result, dict):
        return ValidationResult(False, ["result is not a JSON object"])

    for f in REQUIRED_FIELDS:
        if f not in result:
            errors.append(f"missing field: {f}")
        elif f != "confidence" and _is_empty(result[f]):
            errors.append(f"empty field: {f}")

    level = result.get("complianceLevel")
    if level is not None and level not in _VALID_LEVELS:
        errors.append(f"invalid complianceLevel: {level!r}")

    conf = result.get("confidence")
    if not isinstance(conf, (int, float)):
        errors.append("confidence must be numeric")
    elif not (0.0 <= float(conf) <= 1.0):
        errors.append("confidence out of range [0,1]")

    citations = result.get("citations") or []
    if level != ComplianceLevel.INSUFFICIENT_EVIDENCE.value and len(citations) == 0:
        errors.append("citations required for a supported/decided result (§88)")

    return ValidationResult(not errors, errors)


def detect_hallucinations(
    result: dict, valid_evidence_ids: set, valid_citation_ids: set
) -> ValidationResult:
    """
    §493 Hallucination Detection.

    Every attached citation MUST re-link to a real evidenceId (and, when the
    Context Package enumerates citationIds, to a real citationId). Any citation
    that does not resolve is a fabrication signal -> validation fails so the
    unsupported statement is removed/regenerated (§493 "Unsupported statements
    SHALL be removed").
    """
    errors: List[str] = []
    for c in result.get("citations", []) or []:
        ev_id = c.get("evidenceId")
        if not ev_id or ev_id not in valid_evidence_ids:
            errors.append(f"citation references unknown evidenceId: {ev_id!r}")
        cid = c.get("citationId")
        if cid and valid_citation_ids and cid not in valid_citation_ids:
            errors.append(f"citation references unknown citationId: {cid!r}")
    return ValidationResult(not errors, errors)


# §491 / §91 Human Review Decision -------------------------------------------
def decide_human_review(
    *,
    confidence: float,
    confidence_threshold: float,
    contradictory_evidence: bool,
    missing_citations: bool,
    compliance_level: ComplianceLevel,
    evidence_count: int,
    min_evidence_threshold: int,
    repository_conflict: bool = False,
) -> bool:
    """
    Return True when human review is required (§491/§91). Any single trigger
    is sufficient; the decision is explicit (§491 "Review requirement SHALL be
    explicit").
    """
    if confidence < confidence_threshold:
        return True
    if contradictory_evidence:
        return True
    if missing_citations:
        return True
    if requires_review_by_level(compliance_level):
        return True
    if evidence_count < min_evidence_threshold:
        return True
    if repository_conflict:
        return True
    return False


# §494 Self Validation ordered gate ------------------------------------------
def self_validate(
    result: dict, valid_evidence_ids: set, valid_citation_ids: set
) -> ValidationResult:
    """
    §494 ordered self-validation run before returning output:
      JSON Valid -> Evidence Exists -> Citations Exist -> Compliance Level Valid
      -> Confidence Valid -> Review Decision (presence).
    Combines §264/§90 structural validation with §493 hallucination detection.
    Invalid output SHALL be regenerated (caller retries per §264).
    """
    structural = validate_output(result)
    if not structural.valid:
        return structural

    if _is_empty(result.get("supportingEvidence")) and result.get(
        "complianceLevel"
    ) != ComplianceLevel.INSUFFICIENT_EVIDENCE.value:
        return ValidationResult(False, ["no supporting evidence present (§494)"])

    halluc = detect_hallucinations(result, valid_evidence_ids, valid_citation_ids)
    if not halluc.valid:
        return halluc

    if "reviewRequired" not in result or not isinstance(
        result["reviewRequired"], bool
    ):
        return ValidationResult(False, ["reviewRequired decision missing (§494)"])

    return ValidationResult(True, [])


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False
