# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
"""
SW-023 — Enterprise LLM (reasoning execution boundary).

Governance: §263, R-11, §87 (reasoning rules), §85 (reasoning workflow),
§180 (Compliance Assessment prompt / PR-004).

Scope discipline (R-11): the model produces ONLY the explanation and the
evidence-to-requirement mapping. It does NOT decide `complianceLevel` and does
NOT produce the authoritative `confidence` (R-10). Those are computed by the
platform (compliance_level.py / confidence.py).

The actual LLM call is delegated to the Sprint-1 Provider Adapter layer (the
`invoke` callable injected here), so no provider SDK is embedded and live
provisioning stays in the target deployment (accepted scaffold-then-provision
model). The parser + re-linking below is deterministic and fully testable
against adapter doubles.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

# Type of the injected adapter call: (system, user, model_settings) -> raw text
LLMInvoke = Callable[[str, str, dict], str]


class ReasoningModelError(Exception):
    pass


@dataclass
class ModelReasoningOutput:
    """
    The constrained output SW-023 is allowed to produce (R-11).

    - explanation: free-text reasoning (§485/§87).
    - evidence_mapping: list of {conclusion, evidenceIds:[...]} linking each
      conclusion to the evidence that supports it (§88 citation rule input).
    - evidence_signal: the model's classification of overall evidence support,
      restricted to the §480 signal vocabulary; treated by the platform as the
      matrix key (still deterministic — platform validates + gates it, §481).
    - assumptions / limitations / risks / recommendations: explainability
      fields (§492 / §295), all optional lists.
    - model_self_confidence: advisory ONLY (R-10); never authoritative.
    - suggested_level: advisory ONLY (R-11); never authoritative.
    """

    explanation: str
    evidence_mapping: List[dict]
    evidence_signal: str
    summary: str = ""
    assumptions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    model_self_confidence: Optional[float] = None
    suggested_level: Optional[str] = None


class EnterpriseLLM:
    """SW-023. Wraps the adapter, enforces structured-JSON parsing (§86/§178)."""

    def __init__(self, invoke: LLMInvoke):
        self._invoke = invoke

    def reason(
        self, *, system_prompt: str, user_prompt: str, model_settings: dict
    ) -> ModelReasoningOutput:
        raw = self._invoke(system_prompt, user_prompt, model_settings)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> ModelReasoningOutput:
        text = (raw or "").strip()
        # §178 guardrail: structured JSON only. Strip accidental code fences.
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ReasoningModelError(f"SW-023 returned non-JSON output: {exc}")

        if "explanation" not in data or "evidenceMapping" not in data:
            raise ReasoningModelError(
                "SW-023 output missing required 'explanation'/'evidenceMapping'"
            )

        return ModelReasoningOutput(
            explanation=str(data["explanation"]),
            evidence_mapping=list(data["evidenceMapping"]),
            evidence_signal=str(data.get("evidenceSignal", "missing")),
            summary=str(data.get("summary", "")),
            assumptions=list(data.get("assumptions", [])),
            limitations=list(data.get("limitations", [])),
            risks=list(data.get("risks", [])),
            recommendations=list(data.get("recommendations", [])),
            model_self_confidence=(
                float(data["modelSelfConfidence"])
                if data.get("modelSelfConfidence") is not None
                else None
            ),
            suggested_level=data.get("suggestedLevel"),
        )


# ----------------------------------------------------------------------------
# R-06 — Citation re-linking via evidenceId (§88, §291).
# ----------------------------------------------------------------------------
def relink_citations(
    evidence_objects: List[dict], context_citations: List[dict]
) -> List[dict]:
    """
    Re-link serialized citations to their owning Evidence Object using
    `evidenceId` (R-06). Emits citations in the §291 canonical contract shape:
        {citationId, evidenceId, documentId, page, paragraph, section, locator}

    Sources:
      - evidence_objects: §186 Evidence Objects from the Context Package, each
        carrying its own `citations` and `evidenceId`.
      - context_citations: the Context Package's flat citation list (§294).

    Only citations that round-trip to a known evidenceId are attached (§88: a
    statement without a valid citation SHALL NOT appear; §493 hallucination
    detection removes fabricated citations upstream of this).
    """
    known_evidence_ids = {e.get("evidenceId") for e in evidence_objects if e.get("evidenceId")}
    linked: List[dict] = []
    # De-duplicate by identity key so the same citation is not attached twice
    # when it appears both evidence-owned and in the flat Context list.
    seen: set = set()

    def _key(c: dict) -> tuple:
        cid = c.get("citationId")
        if cid:
            return ("cid", cid)
        return ("tuple", c.get("evidenceId", ""), c.get("documentId", ""),
                c.get("page", 0), c.get("locator", ""))

    # From evidence-owned citations (authoritative FK source, §136/§224).
    for ev in evidence_objects:
        ev_id = ev.get("evidenceId")
        for c in ev.get("citations", []) or []:
            k = _key(c)
            if k not in seen:
                seen.add(k)
                linked.append(_citation_contract(c, ev_id))

    # From the flat context citation list, only where evidenceId re-links.
    for c in context_citations or []:
        ev_id = c.get("evidenceId")
        if ev_id and ev_id in known_evidence_ids:
            k = _key(c)
            if k not in seen:
                seen.add(k)
                linked.append(_citation_contract(c, ev_id))

    return linked


def _citation_contract(c: dict, evidence_id: Optional[str]) -> dict:
    """Project any citation dict onto the §291 canonical Citation contract (R-06)."""
    return {
        "citationId": c.get("citationId", ""),
        "evidenceId": c.get("evidenceId") or (evidence_id or ""),
        "documentId": c.get("documentId", ""),
        "page": c.get("page", 0),
        "paragraph": c.get("paragraph", ""),
        "section": c.get("section", ""),
        "locator": c.get("locator", ""),
    }
