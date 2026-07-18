"""
WF-004 — Output Generation (Proposal Engine deliverables).
All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
Unauthorized copying, modification, distribution, or commercial use is prohibited
without written permission.

Authoritative sources (CRIE_Enterprise_Specification_v1.1.1.md):
  Module 06 §98-§115 (Output Generation); §102/§547 (Compliance Matrix);
  §109/§548 (Executive Summary); §110 (Evidence Report); §111 (Statistics);
  §112 (Audit Trail); §113 (Export Rules — deterministic);
  Module 49 §549 (Gap Analysis), §550 (Risk Register), §551 (review), §552
  (deliverables). Decisions: R-02 (WF-004 = Output Generation; pipeline
  WF-002 -> WF-003 -> WF-004; no WF-006), R-03 (single Compliance Result §295),
  R-04 (Gap/Risk via PR-006/PR-007 — no new prompt IDs), R-08, R-10, R-11.

This module contains NO business reasoning (§98). It formats, aggregates, and
validates the canonical Compliance Results (§295) produced by WF-003 into the
Proposal Package (§552). It never modifies the reasoning result (§99).

The prompt-driven artifacts (proposal Response prose, Gap Analysis, Risk Register,
Executive-Summary narrative) are produced by PR-006/PR-007 via the reasoning layer
(SW-022/SW-023) upstream and arrive attached to each Compliance Result. WF-004
assembles and aggregates them deterministically; it does not call the LLM to invent
new reasoning.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from .sw025_sheets_writer import build_matrix

# Canonical compliance levels (§543 / 16-value enum family; the six decisions).
LEVEL_FULLY = "Fully Compliant"
LEVEL_PARTIAL = "Partially Compliant"
LEVEL_CONFIGURABLE = "Configurable"
LEVEL_CUSTOM = "Custom Development Required"
LEVEL_UNSUPPORTED = "Not Supported"
LEVEL_INSUFFICIENT = "Insufficient Evidence"

_COMPLIANT_FOR_PERCENT = {LEVEL_FULLY, LEVEL_CONFIGURABLE}


class ContractError(ValueError):
    """Raised when an input Compliance Result violates §295 (fail fast, §298)."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ContractError(msg)


def _validate_result(r: Dict[str, Any]) -> None:
    """Fail-fast validation of a single Compliance Result against §295 (§298)."""
    _require(r.get("schemaVersion") == "1.1", "schemaVersion must be '1.1' (§296)")
    for field in ("requirementId", "requirement", "complianceLevel"):
        _require(bool(r.get(field) is not None), f"missing required field '{field}' (§295)")
    conf = r.get("confidence")
    _require(isinstance(conf, (int, float)) and 0 <= conf <= 1,
             "confidence must be a number in [0,1] (§295/R-10)")
    _require(isinstance(r.get("reviewRequired", False), bool),
             "reviewRequired must be boolean (§295)")


def _summ_evidence(r: Dict[str, Any]) -> str:
    ev = r.get("supportingEvidence") or []
    parts: List[str] = []
    for item in ev:
        if isinstance(item, dict):
            parts.append(str(item.get("summary") or item.get("text") or item.get("id") or ""))
        else:
            parts.append(str(item))
    return " | ".join(p for p in parts if p)


def _summ_citations(r: Dict[str, Any]) -> str:
    cites = r.get("citations") or []
    parts: List[str] = []
    for c in cites:
        if isinstance(c, dict):
            doc = c.get("document") or c.get("source") or ""
            page = c.get("page")
            parts.append(f"{doc} p.{page}" if page is not None else str(doc))
        else:
            parts.append(str(c))
    return "; ".join(p for p in parts if p)


# --------------------------------------------------------------------------
# §105 row compliance rules: mark Review Required if any mandatory field missing.
# --------------------------------------------------------------------------
def _apply_row_review_rules(r: Dict[str, Any]) -> bool:
    """Return effective reviewRequired for the matrix row (§105)."""
    if r.get("reviewRequired"):
        return True
    decision_ok = bool(r.get("complianceLevel"))
    explanation_ok = bool(r.get("explanation") or r.get("summary"))
    evidence_ok = bool(r.get("supportingEvidence"))
    citation_ok = bool(r.get("citations"))
    confidence_ok = r.get("confidence") is not None
    return not all([decision_ok, explanation_ok, evidence_ok, citation_ok, confidence_ok])


def build_compliance_matrix_rows(results: List[Dict[str, Any]],
                                 output_config: Dict[str, Any]) -> Dict[str, Any]:
    """Structured Compliance Matrix (§102/§547) — one row per requirement."""
    columns = [c["header"] for c in output_config["complianceMatrix"]["columns"]]
    rows: List[Dict[str, Any]] = []
    for r in results:
        review = r.get("review") or {}
        rows.append({
            "requirementId": r["requirementId"],
            "requirement": r.get("requirement", ""),
            "category": r.get("category"),
            "complianceLevel": r["complianceLevel"],
            "response": r.get("summary", ""),
            "supportingEvidence": _summ_evidence(r),
            "citation": _summ_citations(r),
            "confidence": float(r.get("confidence", 0.0)),
            "reviewRequired": _apply_row_review_rules(r),
            "reviewer": review.get("reviewer"),
            "reviewStatus": review.get("status", output_config["review"]["initialState"]),
        })
    return {"columns": columns, "rows": rows}


def build_executive_summary(results: List[Dict[str, Any]],
                            pr007_narrative: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Executive Summary (§109/§548). Counts and percentages are computed
    deterministically here (R-10/R-11, "validated results only"). keyRisks /
    recommendedNextSteps come from PR-007 narrative if provided, else empty.
    """
    total = len(results)
    counts = {
        LEVEL_FULLY: 0, LEVEL_PARTIAL: 0, LEVEL_CONFIGURABLE: 0,
        LEVEL_CUSTOM: 0, LEVEL_UNSUPPORTED: 0, LEVEL_INSUFFICIENT: 0,
    }
    for r in results:
        lvl = r["complianceLevel"]
        if lvl in counts:
            counts[lvl] += 1
    compliant = sum(counts[l] for l in _COMPLIANT_FOR_PERCENT)
    pct = round((compliant / total) * 100, 2) if total else 0.0
    narrative = pr007_narrative or {}
    return {
        "overallCompliancePercent": pct,
        "totalRequirements": total,
        "fullyCompliantCount": counts[LEVEL_FULLY],
        "partiallyCompliantCount": counts[LEVEL_PARTIAL],
        "configurableCount": counts[LEVEL_CONFIGURABLE],
        "customDevelopmentCount": counts[LEVEL_CUSTOM],
        "unsupportedCount": counts[LEVEL_UNSUPPORTED],
        "insufficientEvidenceCount": counts[LEVEL_INSUFFICIENT],
        "keyRisks": list(narrative.get("keyRisks", [])),
        "recommendedNextSteps": list(narrative.get("recommendedNextSteps", [])),
    }


def build_evidence_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evidence Report (§110): every evidence item used, one row per item."""
    columns = ["requirement", "knowledgeUnit", "evidence", "citation",
               "document", "page", "confidence"]
    rows: List[Dict[str, Any]] = []
    for r in results:
        req = r.get("requirement", "")
        conf = float(r.get("confidence", 0.0))
        kus = r.get("supportingKnowledgeUnits") or [None]
        for ev in (r.get("supportingEvidence") or []):
            if isinstance(ev, dict):
                evidence_text = str(ev.get("summary") or ev.get("text") or ev.get("id") or "")
                doc = ev.get("document") or ev.get("source")
                page = ev.get("page")
                cite = ev.get("citation") or (f"{doc} p.{page}" if doc and page is not None else "")
            else:
                evidence_text, doc, page, cite = str(ev), None, None, ""
            rows.append({
                "requirement": req,
                "knowledgeUnit": kus[0] if kus else None,
                "evidence": evidence_text,
                "citation": cite,
                "document": doc,
                "page": page,
                "confidence": conf,
            })
    return {"columns": columns, "rows": rows}


def build_gap_analysis(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Gap Analysis (§549). Entries originate from PR-006 output attached to each
    result under 'gapAnalysis' (R-04 — no new prompt ID). WF-004 collects and
    tags them with the requirementId; it does not invent gaps.
    """
    items: List[Dict[str, Any]] = []
    for r in results:
        for g in (r.get("gapAnalysis") or []):
            items.append({
                "requirementId": r["requirementId"],
                "gapType": g["gapType"],
                "description": g["description"],
            })
    return {"items": items}


def build_risk_register(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Risk Register (§550). Entries originate from PR-006 output attached to each
    result under 'riskRegister' (R-04 — no new prompt ID).
    """
    items: List[Dict[str, Any]] = []
    for r in results:
        for risk in (r.get("riskRegister") or []):
            items.append({
                "risk": risk["risk"],
                "description": risk["description"],
                "severity": risk["severity"],
                "likelihood": risk["likelihood"],
                "mitigation": risk["mitigation"],
                "owner": risk.get("owner"),
            })
    return {"items": items}


def build_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execution statistics (§111)."""
    total = len(results)
    confs = [float(r.get("confidence", 0.0)) for r in results]
    avg_conf = round(sum(confs) / total, 4) if total else 0.0
    ku = sum(len(r.get("supportingKnowledgeUnits") or []) for r in results)
    ev = sum(len(r.get("supportingEvidence") or []) for r in results)
    cites = sum(len(r.get("citations") or []) for r in results)
    return {
        "requirementsProcessed": total,
        "knowledgeUnitsRetrieved": ku,
        "evidenceObjectsUsed": ev,
        "citationsUsed": cites,
        "averageConfidence": avg_conf,
        "processingTimeMs": None,
        "llmCost": None,
        "embeddingCost": None,
        "totalCost": None,
    }


def build_audit(results: List[Dict[str, Any]],
                context: Dict[str, Any]) -> Dict[str, Any]:
    """Audit trail (§112). repositoryVersion sourced from the results (§295)."""
    repo_version = ""
    generated_at = context.get("generatedAt", "")
    for r in results:
        if r.get("repositoryVersion"):
            repo_version = r["repositoryVersion"]
            break
    return {
        "executionId": context["executionId"],
        "workflowVersion": context.get("workflowVersion", "WF-004@0.8.0"),
        "promptVersion": context.get("promptVersion"),
        "model": context.get("model"),
        "repositoryVersion": repo_version,
        "timestamp": generated_at,
        "reviewer": context.get("reviewer"),
    }


def generate_proposal_package(results: List[Dict[str, Any]],
                              output_config: Dict[str, Any],
                              context: Dict[str, Any],
                              pr007_narrative: Optional[Dict[str, Any]] = None
                              ) -> Dict[str, Any]:
    """
    WF-004 entry point. Deterministically assemble the full Proposal Package
    (§552) from validated Compliance Results (§295). Fail fast on invalid input
    (§298). Does not modify inputs (§99).
    """
    _require(isinstance(results, list) and len(results) > 0,
             "at least one Compliance Result is required (§100)")
    safe_results = copy.deepcopy(results)
    for r in safe_results:
        _validate_result(r)

    package = {
        "schemaVersion": "1.1",
        "proposalId": context["proposalId"],
        "generatedAt": context.get("generatedAt", ""),
        "metadata": {
            "customerName": context.get("customerName"),
            "tenderName": context.get("tenderName"),
            "submissionDate": context.get("submissionDate"),
            "reviewer": context.get("reviewer"),
        },
        "complianceMatrix": build_compliance_matrix_rows(safe_results, output_config),
        "executiveSummary": build_executive_summary(safe_results, pr007_narrative),
        "evidenceReport": build_evidence_report(safe_results),
        "gapAnalysis": build_gap_analysis(safe_results),
        "riskRegister": build_risk_register(safe_results),
        "statistics": build_statistics(safe_results),
        "audit": build_audit(safe_results, context),
    }
    return package


def to_sheets_payload(results: List[Dict[str, Any]],
                      output_config: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience: produce the SW-025 Google Sheets Compliance Matrix payload."""
    return build_matrix(results, output_config)
