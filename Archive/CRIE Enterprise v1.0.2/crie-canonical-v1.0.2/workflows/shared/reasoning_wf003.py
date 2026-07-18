# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
"""
WF-003 — Enterprise Reasoning orchestrator.

Governance: §156 (WF-003 execution), §85 (reasoning workflow), R-03 (single
Compliance Result contract §295). Consumes the Sprint-5 Context Package (§261/
§294) as its ONLY input (per PROJECT_STATUS Next Sprint Goal and §156 trigger).

Execution (§156):
  Receive Context -> Validate Context -> Load Prompt (PR-004) -> Enterprise LLM
  -> Validate JSON (SW-024) -> Attach Citations (R-06) -> Confidence (R-10)
  -> Return Compliance Result (§295)

Deterministic ordering per R-11: the model contributes explanation + evidence
mapping; the platform derives complianceLevel and computes confidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from .compliance_level import derive_compliance_level
from .confidence import ConfidenceInputs, ConfidenceWeights, compute_confidence
from .enterprise_llm import EnterpriseLLM, relink_citations
from .output_validator import decide_human_review, self_validate
from .prompt_loader import PromptLoader

SCHEMA_VERSION = "1.1"


class ContextPackageError(Exception):
    pass


class ReasoningExecutionError(Exception):
    pass


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_context(cp: dict) -> None:
    """§156 Validate Context / §298 fail-fast input contract check."""
    if not isinstance(cp, dict):
        raise ContextPackageError("Context Package is not an object")
    for f in ("contextId", "requirement", "knowledgeUnits", "evidence", "citations"):
        if f not in cp:
            raise ContextPackageError(f"Context Package missing field: {f}")


def _consistency_from_conflict(cp: dict) -> float:
    """§482: contradictory evidence reduces confidence. 1.0 = no conflict."""
    stats = cp.get("statistics") or cp.get("retrievalStatistics") or {}
    conflicts = int(stats.get("conflictCount", 0))
    if conflicts <= 0:
        return 1.0
    # Monotonic decreasing penalty, floored at 0.
    return max(0.0, 1.0 - min(conflicts, 5) * 0.2)


def _mean_evidence_quality(evidence: List[dict]) -> float:
    vals = [float(e.get("confidence", 0.0)) for e in evidence if e is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _normalized_authority(evidence: List[dict]) -> float:
    """Normalize §439 authority (0-100) to [0,1] over supporting evidence."""
    scores: List[float] = []
    for e in evidence:
        a = e.get("authority")
        if isinstance(a, (int, float)):
            scores.append(float(a))
        elif isinstance(a, str) and a.strip():
            # Textual authority label without a numeric score contributes 0.
            scores.append(0.0)
    return (sum(scores) / len(scores) / 100.0) if scores else 0.0


def _citation_coverage(evidence_mapping: List[dict]) -> float:
    """§88: fraction of model conclusions that carry >=1 evidence link."""
    if not evidence_mapping:
        return 0.0
    covered = sum(1 for m in evidence_mapping if m.get("evidenceIds"))
    return covered / len(evidence_mapping)


def run_wf003(
    *,
    context_package: dict,
    prompt_loader: PromptLoader,
    enterprise_llm: EnterpriseLLM,
    weights: ConfidenceWeights,
    confidence_threshold: float,
    min_evidence_threshold: int,
    prompt_id: str = "PR-004",
    prompt_version: Optional[str] = None,
    repository_version: str = "",
    customer: str = "",
    language: str = "en",
    max_retries: int = 1,
) -> dict:
    """
    Execute WF-003 and return a single §295 Compliance Result dict.

    Retries (§264/§494 "Invalid output SHALL be regenerated") up to max_retries
    when self-validation fails.
    """
    _validate_context(context_package)

    prompt = prompt_loader.load(prompt_id, prompt_version)
    user_prompt = PromptLoader.inject(
        prompt,
        {
            "requirement": context_package.get("requirement", ""),
            "context": _render_context(context_package),
            "citations": _render_citations(context_package.get("citations", [])),
            "knowledge": _render_knowledge(context_package.get("knowledgeUnits", [])),
            "customer": customer,
            "language": language,
        },
    )

    evidence = context_package.get("evidence", []) or []
    knowledge_units = context_package.get("knowledgeUnits", []) or []

    # R-06: re-link citations up front so downstream checks use canonical shape.
    linked_citations = relink_citations(evidence, context_package.get("citations", []))
    valid_evidence_ids = {e.get("evidenceId") for e in evidence if e.get("evidenceId")}
    valid_citation_ids = {
        c.get("citationId") for c in linked_citations if c.get("citationId")
    }

    last_errors: List[str] = []
    for _attempt in range(max_retries + 1):
        model_out = enterprise_llm.reason(
            system_prompt=prompt.system_prompt,
            user_prompt=user_prompt,
            model_settings=_model_settings_dict(prompt),
        )

        # R-11: derive complianceLevel deterministically.
        level = derive_compliance_level(
            knowledge_unit_count=len(knowledge_units),
            evidence_count=len(evidence),
            citation_count=len(linked_citations),
            evidence_signal=model_out.evidence_signal,
        )

        # R-10: platform-computed confidence.
        conf_inputs = ConfidenceInputs(
            retrieval_confidence=float(
                context_package.get("confidence")
                or context_package.get("retrievalConfidence")
                or 0.0
            ),
            evidence_quality=_mean_evidence_quality(evidence),
            authority=_normalized_authority(evidence),
            citation_coverage=_citation_coverage(model_out.evidence_mapping),
            consistency=_consistency_from_conflict(context_package),
        )
        confidence = compute_confidence(conf_inputs, weights)

        contradictory = _consistency_from_conflict(context_package) < 1.0
        review_required = decide_human_review(
            confidence=confidence,
            confidence_threshold=confidence_threshold,
            contradictory_evidence=contradictory,
            missing_citations=(len(linked_citations) == 0),
            compliance_level=level,
            evidence_count=len(evidence),
            min_evidence_threshold=min_evidence_threshold,
            repository_conflict=contradictory,
        )

        result = _assemble_result(
            context_package=context_package,
            level=level,
            confidence=confidence,
            model_out=model_out,
            citations=linked_citations,
            review_required=review_required,
            repository_version=repository_version,
        )

        check = self_validate(result, valid_evidence_ids, valid_citation_ids)
        if check.valid:
            return result
        last_errors = check.errors

    raise ReasoningExecutionError(
        f"WF-003 output failed self-validation after retries: {last_errors}"
    )


def _assemble_result(
    *,
    context_package: dict,
    level,
    confidence: float,
    model_out,
    citations: List[dict],
    review_required: bool,
    repository_version: str,
) -> dict:
    """Emit the single canonical §295 Compliance Result contract (R-03)."""
    supporting_evidence = [
        e.get("evidenceId") for e in context_package.get("evidence", []) if e.get("evidenceId")
    ]
    supporting_kus = [
        k.get("knowledgeUnitId") or k.get("id")
        for k in context_package.get("knowledgeUnits", [])
        if (k.get("knowledgeUnitId") or k.get("id"))
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "requirementId": context_package.get("requirementId")
        or context_package.get("contextId", ""),
        "requirement": context_package.get("requirement", ""),
        "decision": level.value,
        "complianceLevel": level.value,
        "confidence": confidence,
        "summary": model_out.summary,
        "explanation": model_out.explanation,
        "supportingEvidence": supporting_evidence,
        "supportingKnowledgeUnits": supporting_kus,
        "citations": citations,
        "assumptions": model_out.assumptions,
        "limitations": model_out.limitations,
        "risks": model_out.risks,
        "recommendations": model_out.recommendations,
        "reviewRequired": review_required,
        "repositoryVersion": repository_version,
        "generatedAt": _iso_now(),
    }


def _model_settings_dict(prompt) -> dict:
    ms = prompt.model_settings
    return {
        "provider": ms.provider,
        "model": ms.model,
        "temperature": ms.temperature,
        "topP": ms.top_p,
        "maxTokens": ms.max_tokens,
        "frequencyPenalty": ms.frequency_penalty,
        "presencePenalty": ms.presence_penalty,
        "timeout": ms.timeout,
    }


def _render_context(cp: dict) -> str:
    ev = cp.get("evidence", []) or []
    return "\n".join(
        f"- [{e.get('evidenceId','')}] ({e.get('authority','')}) {e.get('text','')}"
        for e in ev
    )


def _render_citations(citations: List[dict]) -> str:
    return "\n".join(
        f"- {c.get('citationId','')} -> evidence {c.get('evidenceId','')} "
        f"(doc {c.get('documentId','')}, p.{c.get('page',0)})"
        for c in (citations or [])
    )


def _render_knowledge(kus: List[dict]) -> str:
    return "\n".join(
        f"- [{k.get('knowledgeUnitId', k.get('id',''))}] {k.get('text','')}"
        for k in (kus or [])
    )
