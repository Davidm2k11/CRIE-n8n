# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
"""
Sprint 6 acceptance tests — Enterprise Reasoning (WF-003).

Maps each test to a backlog item S6-1..S6-9 and its DoD: a valid Compliance
Result produced against the single canonical §295 contract. Uses in-memory
adapter doubles (accepted "no live datastore/provider" model) that drive the
real deterministic logic.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _pathsetup  # noqa: E402,F401

from reasoning.compliance_level import (  # noqa: E402
    ComplianceLevel,
    derive_compliance_level,
    evidence_sufficient,
)
from reasoning.confidence import (  # noqa: E402
    ConfidenceInputs,
    ConfidenceWeights,
    compute_confidence,
    interpret_confidence,
)
from reasoning.enterprise_llm import EnterpriseLLM, relink_citations  # noqa: E402
from reasoning.output_validator import (  # noqa: E402
    decide_human_review,
    detect_hallucinations,
    self_validate,
    validate_output,
)
from reasoning.prompt_loader import (  # noqa: E402
    MissingVariableError,
    PromptLoader,
    PromptNotFoundError,
)
from reasoning.wf003 import run_wf003  # noqa: E402


WEIGHTS = ConfidenceWeights(0.30, 0.25, 0.20, 0.15, 0.10)


def _registry():
    return {
        "PR-004": {
            "1.0": {
                "purpose": "Compliance Assessment",
                "systemPrompt": "system rules",
                "userTemplate": "R:{{requirement}} C:{{context}} "
                "CIT:{{citations}} K:{{knowledge}} CUST:{{customer}} L:{{language}}",
                "variables": [
                    "requirement",
                    "context",
                    "citations",
                    "knowledge",
                    "customer",
                    "language",
                ],
                "guardrails": ["Return structured JSON only."],
                "modelSettings": {
                    "provider": "p",
                    "model": "m",
                    "temperature": 0.0,
                    "topP": 1.0,
                    "maxTokens": 4096,
                    "frequencyPenalty": 0.0,
                    "presencePenalty": 0.0,
                    "timeout": 60,
                },
            }
        }
    }


def _context_package(signal="strong_supporting", conflicts=0):
    return {
        "contextId": "ctx-1",
        "requirementId": "REQ-1",
        "requirement": "System must support SSO via SAML.",
        "confidence": 0.82,
        "knowledgeUnits": [{"knowledgeUnitId": "KU-1", "text": "SAML SSO supported."}],
        "evidence": [
            {
                "evidenceId": "EV-1",
                "knowledgeUnitId": "KU-1",
                "type": "capability",
                "text": "Product supports SAML 2.0 SSO.",
                "confidence": 0.9,
                "authority": 100,
                "citations": [
                    {
                        "citationId": "CI-1",
                        "evidenceId": "EV-1",
                        "documentId": "DOC-1",
                        "page": 12,
                        "paragraph": "2",
                        "section": "Security",
                        "locator": "p12",
                    }
                ],
            }
        ],
        "citations": [
            {
                "citationId": "CI-1",
                "evidenceId": "EV-1",
                "documentId": "DOC-1",
                "page": 12,
            }
        ],
        "statistics": {"conflictCount": conflicts},
        "_signal": signal,
    }


def _fake_invoke_factory(signal, self_conf=0.7, mapping_covered=True):
    def _invoke(system, user, settings):
        mapping = [{"conclusion": "SSO supported", "evidenceIds": ["EV-1"]}]
        if not mapping_covered:
            mapping = [{"conclusion": "SSO supported", "evidenceIds": []}]
        return json.dumps(
            {
                "explanation": "Evidence EV-1 shows SAML 2.0 SSO support.",
                "summary": "Requirement is met.",
                "evidenceSignal": signal,
                "evidenceMapping": mapping,
                "assumptions": [],
                "limitations": [],
                "risks": [],
                "recommendations": [],
                "suggestedLevel": "Fully Compliant",
                "modelSelfConfidence": self_conf,
            }
        )

    return _invoke


class S61PromptLoader(unittest.TestCase):
    def test_loads_pr004(self):
        p = PromptLoader(_registry()).load("PR-004", "1.0")
        self.assertEqual(p.prompt_id, "PR-004")
        self.assertEqual(p.model_settings.temperature, 0.0)

    def test_resolves_latest_version(self):
        p = PromptLoader(_registry()).load("PR-004")
        self.assertEqual(p.version, "1.0")

    def test_unknown_prompt_raises(self):
        with self.assertRaises(PromptNotFoundError):
            PromptLoader(_registry()).load("PR-999")

    def test_missing_variable_stops_execution(self):
        loader = PromptLoader(_registry())
        p = loader.load("PR-004", "1.0")
        with self.assertRaises(MissingVariableError):
            loader.inject(p, {"requirement": "x"})  # others missing

    def test_variable_injection(self):
        loader = PromptLoader(_registry())
        p = loader.load("PR-004", "1.0")
        out = loader.inject(
            p,
            {
                "requirement": "REQ",
                "context": "CTX",
                "citations": "CIT",
                "knowledge": "K",
                "customer": "Acme",
                "language": "en",
            },
        )
        self.assertIn("R:REQ", out)
        self.assertIn("CUST:Acme", out)


class S62EnterpriseLLM(unittest.TestCase):
    def test_produces_explanation_and_mapping_only(self):
        llm = EnterpriseLLM(_fake_invoke_factory("strong_supporting"))
        out = llm.reason(system_prompt="s", user_prompt="u", model_settings={})
        self.assertTrue(out.explanation)
        self.assertTrue(out.evidence_mapping)
        # advisory-only fields captured, never authoritative
        self.assertEqual(out.suggested_level, "Fully Compliant")
        self.assertEqual(out.model_self_confidence, 0.7)

    def test_rejects_non_json(self):
        llm = EnterpriseLLM(lambda s, u, m: "not json")
        with self.assertRaises(Exception):
            llm.reason(system_prompt="s", user_prompt="u", model_settings={})


class S63ComplianceLevel(unittest.TestCase):
    def test_matrix_mapping(self):
        cases = {
            "strong_supporting": ComplianceLevel.FULLY_COMPLIANT,
            "partial": ComplianceLevel.PARTIALLY_COMPLIANT,
            "configuration_available": ComplianceLevel.CONFIGURABLE,
            "requires_customization": ComplianceLevel.CUSTOM_DEVELOPMENT_REQUIRED,
            "strong_contradictory": ComplianceLevel.NOT_SUPPORTED,
            "missing": ComplianceLevel.INSUFFICIENT_EVIDENCE,
        }
        for signal, expected in cases.items():
            self.assertEqual(
                derive_compliance_level(
                    knowledge_unit_count=1,
                    evidence_count=1,
                    citation_count=1,
                    evidence_signal=signal,
                ),
                expected,
            )

    def test_sufficiency_gate_overrides_signal(self):
        # §481: missing citation forces Insufficient Evidence even if signal is strong
        self.assertEqual(
            derive_compliance_level(
                knowledge_unit_count=1,
                evidence_count=1,
                citation_count=0,
                evidence_signal="strong_supporting",
            ),
            ComplianceLevel.INSUFFICIENT_EVIDENCE,
        )

    def test_unknown_signal_fails_safe(self):
        self.assertEqual(
            derive_compliance_level(
                knowledge_unit_count=1,
                evidence_count=1,
                citation_count=1,
                evidence_signal="banana",
            ),
            ComplianceLevel.INSUFFICIENT_EVIDENCE,
        )

    def test_evidence_sufficient_helper(self):
        self.assertTrue(evidence_sufficient(1, 1, 1))
        self.assertFalse(evidence_sufficient(0, 1, 1))


class S64Confidence(unittest.TestCase):
    def test_platform_computes_in_range(self):
        inp = ConfidenceInputs(0.8, 0.9, 1.0, 1.0, 1.0)
        c = compute_confidence(inp, WEIGHTS)
        self.assertGreaterEqual(c, 0.0)
        self.assertLessEqual(c, 1.0)

    def test_deterministic(self):
        inp = ConfidenceInputs(0.8, 0.9, 1.0, 1.0, 1.0)
        self.assertEqual(
            compute_confidence(inp, WEIGHTS), compute_confidence(inp, WEIGHTS)
        )

    def test_model_self_confidence_not_used(self):
        # confidence depends only on platform signals; no self-confidence input exists
        low = compute_confidence(ConfidenceInputs(0.1, 0.1, 0.1, 0.1, 0.1), WEIGHTS)
        high = compute_confidence(ConfidenceInputs(0.9, 0.9, 0.9, 0.9, 0.9), WEIGHTS)
        self.assertLess(low, high)

    def test_interpretation_bands(self):
        self.assertEqual(interpret_confidence(0.97), "Extremely High")
        self.assertEqual(interpret_confidence(0.40), "Human Review Required")

    def test_zero_weights_raise(self):
        with self.assertRaises(ValueError):
            compute_confidence(
                ConfidenceInputs(1, 1, 1, 1, 1),
                ConfidenceWeights(0, 0, 0, 0, 0),
            )


class S65OutputValidator(unittest.TestCase):
    def _good_result(self):
        return {
            "schemaVersion": "1.1",
            "requirementId": "REQ-1",
            "requirement": "r",
            "decision": "Fully Compliant",
            "complianceLevel": "Fully Compliant",
            "confidence": 0.9,
            "explanation": "because EV-1",
            "supportingEvidence": ["EV-1"],
            "citations": [{"citationId": "CI-1", "evidenceId": "EV-1"}],
            "reviewRequired": False,
            "generatedAt": "2026-07-07T00:00:00Z",
        }

    def test_valid_passes(self):
        self.assertTrue(validate_output(self._good_result()).valid)

    def test_missing_field_fails(self):
        r = self._good_result()
        del r["confidence"]
        self.assertFalse(validate_output(r).valid)

    def test_bad_level_fails(self):
        r = self._good_result()
        r["complianceLevel"] = "Sorta Compliant"
        self.assertFalse(validate_output(r).valid)

    def test_confidence_out_of_range_fails(self):
        r = self._good_result()
        r["confidence"] = 1.5
        self.assertFalse(validate_output(r).valid)


class S66Citations(unittest.TestCase):
    def test_relink_via_evidence_id(self):
        cp = _context_package()
        linked = relink_citations(cp["evidence"], cp["citations"])
        self.assertTrue(linked)
        for c in linked:
            self.assertEqual(c["evidenceId"], "EV-1")
            # §291 canonical shape keys present
            for k in (
                "citationId",
                "evidenceId",
                "documentId",
                "page",
                "paragraph",
                "section",
                "locator",
            ):
                self.assertIn(k, c)


class S67Hallucination(unittest.TestCase):
    def test_detects_unknown_evidence_id(self):
        result = {"citations": [{"citationId": "X", "evidenceId": "GHOST"}]}
        res = detect_hallucinations(result, {"EV-1"}, {"CI-1"})
        self.assertFalse(res.valid)

    def test_passes_known(self):
        result = {"citations": [{"citationId": "CI-1", "evidenceId": "EV-1"}]}
        res = detect_hallucinations(result, {"EV-1"}, {"CI-1"})
        self.assertTrue(res.valid)


class S68HumanReview(unittest.TestCase):
    def test_low_confidence_triggers(self):
        self.assertTrue(
            decide_human_review(
                confidence=0.4,
                confidence_threshold=0.65,
                contradictory_evidence=False,
                missing_citations=False,
                compliance_level=ComplianceLevel.FULLY_COMPLIANT,
                evidence_count=3,
                min_evidence_threshold=1,
            )
        )

    def test_custom_dev_triggers(self):
        self.assertTrue(
            decide_human_review(
                confidence=0.99,
                confidence_threshold=0.65,
                contradictory_evidence=False,
                missing_citations=False,
                compliance_level=ComplianceLevel.CUSTOM_DEVELOPMENT_REQUIRED,
                evidence_count=3,
                min_evidence_threshold=1,
            )
        )

    def test_clean_high_conf_no_review(self):
        self.assertFalse(
            decide_human_review(
                confidence=0.95,
                confidence_threshold=0.65,
                contradictory_evidence=False,
                missing_citations=False,
                compliance_level=ComplianceLevel.FULLY_COMPLIANT,
                evidence_count=3,
                min_evidence_threshold=1,
            )
        )


class S69EndToEndContract(unittest.TestCase):
    def _run(self, signal="strong_supporting", conflicts=0, covered=True):
        cp = _context_package(signal=signal, conflicts=conflicts)
        return run_wf003(
            context_package=cp,
            prompt_loader=PromptLoader(_registry()),
            enterprise_llm=EnterpriseLLM(
                _fake_invoke_factory(signal, mapping_covered=covered)
            ),
            weights=WEIGHTS,
            confidence_threshold=0.65,
            min_evidence_threshold=1,
            repository_version="repo-2026.07",
        )

    def test_emits_canonical_contract(self):
        result = self._run()
        contract_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "schemas",
            "contracts",
            "compliance_result.contract.json",
        )
        with open(contract_path) as f:
            contract = json.load(f)
        expected_fields = {k for k in contract if not k.startswith("$")}
        self.assertEqual(set(result.keys()), expected_fields)

    def test_fully_compliant_path(self):
        result = self._run("strong_supporting")
        self.assertEqual(result["complianceLevel"], "Fully Compliant")
        self.assertEqual(result["decision"], "Fully Compliant")
        self.assertFalse(result["reviewRequired"])
        self.assertTrue(result["citations"])

    def test_insufficient_evidence_forces_review(self):
        result = self._run("missing")
        # signal 'missing' -> Insufficient Evidence -> review required (§491)
        self.assertEqual(result["complianceLevel"], "Insufficient Evidence")
        self.assertTrue(result["reviewRequired"])

    def test_conflict_reduces_and_flags(self):
        result = self._run("strong_supporting", conflicts=3)
        self.assertTrue(result["reviewRequired"])  # §482 conflict -> review

    def test_confidence_is_platform_value(self):
        result = self._run("strong_supporting")
        self.assertIsInstance(result["confidence"], float)
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)

    def test_repository_version_propagated(self):
        result = self._run()
        self.assertEqual(result["repositoryVersion"], "repo-2026.07")


if __name__ == "__main__":
    unittest.main(verbosity=2)
