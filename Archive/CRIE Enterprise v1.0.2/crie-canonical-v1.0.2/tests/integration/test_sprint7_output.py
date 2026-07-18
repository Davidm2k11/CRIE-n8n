"""
Sprint 7 acceptance tests — Proposal Engine (WF-004 Output Generation).
All Rights Reserved, Copyright (c) 2026 Dawod Manasra.

Covers §114 acceptance criteria, the Sprint-7 DoD exit gate (complete Proposal
Package from a sample requirement set), export determinism (§113), configurable
column mapping (§364), review workflow (§106/§107/§551), and the R-02/R-03/R-04
sprint-isolation guards. Runnable with the stdlib only (no live datastore/LLM).
"""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import _pathsetup  # noqa: E402,F401

from output_generation import wf004_output_generation as wf004  # noqa: E402
from output_generation import sw025_sheets_writer as sw025      # noqa: E402
from output_generation import review_workflow as rw             # noqa: E402

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..", "..")  # canonical repository root


def load_yaml_config():
    """Minimal YAML loader for output.config.yaml without external deps.
    Uses PyYAML if available, else a tiny fallback for the fields we assert."""
    path = os.path.join(ROOT, "configuration", "output.yaml")
    try:
        import yaml  # type: ignore
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def load_config():
    cfg = load_yaml_config()
    if cfg is not None:
        return cfg
    # Fallback config mirroring output.config.yaml for environments without PyYAML.
    return {
        "complianceMatrix": {
            "columns": [
                {"key": "requirementId", "header": "Requirement ID", "source": "requirementId", "sheetsColumn": "A"},
                {"key": "requirement", "header": "Requirement", "source": "requirement", "sheetsColumn": "B"},
                {"key": "category", "header": "Category", "source": "category", "sheetsColumn": "C"},
                {"key": "complianceLevel", "header": "Compliance Level", "source": "complianceLevel", "sheetsColumn": "D"},
                {"key": "response", "header": "Response", "source": "summary", "sheetsColumn": "E"},
                {"key": "supportingEvidence", "header": "Supporting Evidence", "source": "supportingEvidence", "sheetsColumn": "F"},
                {"key": "citation", "header": "Citation", "source": "citations", "sheetsColumn": "G"},
                {"key": "confidence", "header": "Confidence", "source": "confidence", "sheetsColumn": "H"},
                {"key": "reviewRequired", "header": "Review Required", "source": "reviewRequired", "sheetsColumn": "I"},
                {"key": "reviewer", "header": "Reviewer", "source": "review.reviewer", "sheetsColumn": "J"},
                {"key": "reviewStatus", "header": "Review Status", "source": "review.status", "sheetsColumn": "K"},
            ]
        },
        "googleSheets": {
            "freezeHeaderRow": True,
            "tabs": {"complianceMatrix": "Compliance Matrix"},
        },
        "review": {"initialState": "Pending"},
    }


def load_samples():
    path = os.path.join(ROOT, "examples", "rfps", "sample_requirements.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_context():
    return {
        "proposalId": "PROP-0007",
        "executionId": "EXEC-0007",
        "workflowVersion": "WF-004@0.8.0",
        "generatedAt": "2026-07-07T10:00:00Z",
        "customerName": "Acme Corp",
        "tenderName": "RFP-2026-42",
        "reviewer": "J. Reviewer",
        "model": "provider-model-x",
        "promptVersion": "PR-006@1.0,PR-007@1.0",
    }


class TestComplianceMatrix(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.results = load_samples()

    def test_one_row_per_requirement(self):
        # §102/§547: each requirement produces exactly one row.
        matrix = wf004.build_compliance_matrix_rows(self.results, self.cfg)
        self.assertEqual(len(matrix["rows"]), len(self.results))

    def test_required_columns_present(self):
        # §102 required columns.
        matrix = wf004.build_compliance_matrix_rows(self.results, self.cfg)
        row = matrix["rows"][0]
        for field in ("requirementId", "requirement", "category", "complianceLevel",
                      "response", "supportingEvidence", "citation", "confidence",
                      "reviewRequired", "reviewer", "reviewStatus"):
            self.assertIn(field, row)

    def test_confidence_preserved(self):
        # §114: confidence preserved (platform-computed, R-10).
        matrix = wf004.build_compliance_matrix_rows(self.results, self.cfg)
        self.assertAlmostEqual(matrix["rows"][0]["confidence"], 0.94)

    def test_citations_preserved(self):
        # §114: citations preserved.
        matrix = wf004.build_compliance_matrix_rows(self.results, self.cfg)
        self.assertIn("Security Configuration Guide", matrix["rows"][0]["citation"])

    def test_row_review_rule_marks_missing_evidence(self):
        # §105: row with no evidence/citation must be marked Review Required.
        matrix = wf004.build_compliance_matrix_rows(self.results, self.cfg)
        req004 = next(r for r in matrix["rows"] if r["requirementId"] == "REQ-004")
        self.assertTrue(req004["reviewRequired"])


class TestSheetsWriter(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.results = load_samples()

    def test_no_hardcoded_columns_uses_config_letters(self):
        # §364: mapping is configuration-driven; keys are the configured letters.
        payload = sw025.build_matrix(self.results, self.cfg)
        self.assertEqual(set(payload["rows"][0].keys()),
                         {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"})

    def test_header_from_config(self):
        header = sw025.build_header(self.cfg)
        self.assertEqual(header["A"], "Requirement ID")
        self.assertEqual(header["D"], "Compliance Level")

    def test_freeze_header_flag(self):
        payload = sw025.build_matrix(self.results, self.cfg)
        self.assertTrue(payload["freezeHeaderRow"])


class TestExecutiveSummary(unittest.TestCase):
    def setUp(self):
        self.results = load_samples()

    def test_counts(self):
        # §109/§548 counts.
        summ = wf004.build_executive_summary(self.results)
        self.assertEqual(summ["totalRequirements"], 5)
        self.assertEqual(summ["fullyCompliantCount"], 1)
        self.assertEqual(summ["partiallyCompliantCount"], 1)
        self.assertEqual(summ["configurableCount"], 1)
        self.assertEqual(summ["customDevelopmentCount"], 1)
        self.assertEqual(summ["insufficientEvidenceCount"], 1)
        self.assertEqual(summ["unsupportedCount"], 0)

    def test_overall_percent_deterministic(self):
        # Fully Compliant + Configurable count toward compliance %: 2/5 = 40%.
        summ = wf004.build_executive_summary(self.results)
        self.assertEqual(summ["overallCompliancePercent"], 40.0)

    def test_narrative_from_pr007(self):
        summ = wf004.build_executive_summary(
            self.results,
            {"keyRisks": ["risk A"], "recommendedNextSteps": ["step A"]},
        )
        self.assertEqual(summ["keyRisks"], ["risk A"])
        self.assertEqual(summ["recommendedNextSteps"], ["step A"])


class TestEvidenceReport(unittest.TestCase):
    def test_columns_and_rows(self):
        # §110 evidence report columns.
        report = wf004.build_evidence_report(load_samples())
        self.assertEqual(report["columns"],
                         ["requirement", "knowledgeUnit", "evidence", "citation",
                          "document", "page", "confidence"])
        # 4 requirements carry evidence (REQ-004 has none).
        self.assertEqual(len(report["rows"]), 4)


class TestGapAndRisk(unittest.TestCase):
    def setUp(self):
        self.results = load_samples()

    def test_gap_types_valid(self):
        # §549: only the three allowed gap types; produced by PR-006 (R-04).
        gaps = wf004.build_gap_analysis(self.results)["items"]
        allowed = {"Documentation Gap", "Product Gap", "Knowledge Gap"}
        self.assertTrue(all(g["gapType"] in allowed for g in gaps))
        self.assertEqual(len(gaps), 3)

    def test_risk_fields(self):
        # §550 required fields.
        risks = wf004.build_risk_register(self.results)["items"]
        self.assertEqual(len(risks), 2)
        for r in risks:
            for f in ("risk", "description", "severity", "likelihood", "mitigation", "owner"):
                self.assertIn(f, r)


class TestReviewWorkflow(unittest.TestCase):
    def test_legal_transition(self):
        self.assertEqual(rw.transition("Pending", "In Review"), "In Review")
        self.assertEqual(rw.transition("In Review", "Approved"), "Approved")

    def test_illegal_transition_raises(self):
        with self.assertRaises(rw.ReviewError):
            rw.transition("Approved", "In Review")

    def test_reject_routes_to_reasoning(self):
        # §106/§551: rejected -> WF-003.
        directive = rw.route_on_reject({"requirementId": "REQ-002"})
        self.assertEqual(directive["target"], "WF-003")
        self.assertEqual(directive["action"], "return-to-reasoning")

    def test_publish_gate(self):
        self.assertTrue(rw.can_publish("Approved"))
        self.assertFalse(rw.can_publish("In Review"))

    def test_apply_review_does_not_mutate_input(self):
        result = {"requirementId": "REQ-001"}
        updated = rw.apply_review(result, "Assigned", reviewer="X")
        self.assertNotIn("review", result)  # input untouched (§99)
        self.assertEqual(updated["review"]["status"], "Assigned")
        self.assertEqual(updated["review"]["reviewer"], "X")


class TestExportDeterminism(unittest.TestCase):
    def test_deterministic_export(self):
        # §113: identical inputs produce identical outputs.
        cfg, results, ctx = load_config(), load_samples(), make_context()
        p1 = wf004.generate_proposal_package(results, cfg, ctx)
        p2 = wf004.generate_proposal_package(copy.deepcopy(results), cfg, ctx)
        self.assertEqual(json.dumps(p1, sort_keys=True), json.dumps(p2, sort_keys=True))

    def test_input_not_mutated(self):
        cfg, results, ctx = load_config(), load_samples(), make_context()
        snapshot = json.dumps(results, sort_keys=True)
        wf004.generate_proposal_package(results, cfg, ctx)
        self.assertEqual(json.dumps(results, sort_keys=True), snapshot)


class TestContractValidation(unittest.TestCase):
    def test_fail_fast_on_bad_schema_version(self):
        cfg, results, ctx = load_config(), load_samples(), make_context()
        bad = copy.deepcopy(results)
        bad[0]["schemaVersion"] = "1.0"
        with self.assertRaises(wf004.ContractError):
            wf004.generate_proposal_package(bad, cfg, ctx)

    def test_fail_fast_on_missing_field(self):
        cfg, results, ctx = load_config(), load_samples(), make_context()
        bad = copy.deepcopy(results)
        del bad[0]["complianceLevel"]
        with self.assertRaises(wf004.ContractError):
            wf004.generate_proposal_package(bad, cfg, ctx)

    def test_fail_fast_on_empty_input(self):
        cfg, ctx = load_config(), make_context()
        with self.assertRaises(wf004.ContractError):
            wf004.generate_proposal_package([], cfg, ctx)


class TestExitGate(unittest.TestCase):
    """DoD: complete Proposal Package generated from a sample requirement set."""

    def setUp(self):
        self.cfg = load_config()
        self.results = load_samples()
        self.ctx = make_context()
        self.pkg = wf004.generate_proposal_package(
            self.results, self.cfg, self.ctx,
            pr007_narrative={"keyRisks": ["ISO 27001 evidence missing"],
                             "recommendedNextSteps": ["Certify ISO docs"]},
        )

    def test_all_deliverables_present(self):
        # §552 proposal deliverables (v1 subset produced by WF-004).
        for key in ("complianceMatrix", "executiveSummary", "evidenceReport",
                    "gapAnalysis", "riskRegister", "statistics", "audit"):
            self.assertIn(key, self.pkg)

    def test_matches_contract_shape(self):
        # Validate against proposal_package.contract.json if jsonschema available.
        with open(os.path.join(ROOT, "schemas", "contracts", "proposal_package.contract.json"),
                  "r", encoding="utf-8") as f:
            schema = json.load(f)
        try:
            import jsonschema  # type: ignore
            jsonschema.validate(self.pkg, schema)
        except ImportError:
            # Structural fallback assertions.
            self.assertEqual(self.pkg["schemaVersion"], "1.1")
            self.assertEqual(self.pkg["proposalId"], "PROP-0007")

    def test_audit_trail_preserved(self):
        # §112 audit fields.
        audit = self.pkg["audit"]
        self.assertEqual(audit["executionId"], "EXEC-0007")
        self.assertEqual(audit["repositoryVersion"], "repo-2026.06")
        self.assertEqual(audit["reviewer"], "J. Reviewer")

    def test_statistics_present(self):
        stats = self.pkg["statistics"]
        self.assertEqual(stats["requirementsProcessed"], 5)
        self.assertTrue(0 <= stats["averageConfidence"] <= 1)


class TestSprintIsolation(unittest.TestCase):
    """Guards ensuring no Sprint-8 (Administration/WF-005) scope leaks in."""

    def test_no_wf005_reference_in_source(self):
        # Canonical layout: output modules are workflows/shared/output_*.py
        src_dir = os.path.join(ROOT, "workflows", "shared")
        for name in os.listdir(src_dir):
            if name.startswith("output_") and name.endswith(".py"):
                with open(os.path.join(src_dir, name), "r", encoding="utf-8") as f:
                    content = f.read()
                self.assertNotIn("WF-005", content,
                                 f"{name} must not reference WF-005 (Sprint 8)")

    def test_no_new_prompt_ids_beyond_catalog(self):
        # R-04: no PR-009+ introduced.
        for pr in ("PR-009", "PR-010", "PR-011"):
            for root_dir, _dirs, files in os.walk(os.path.join(ROOT, "prompts")):
                for fn in files:
                    with open(os.path.join(root_dir, fn), "r", encoding="utf-8") as f:
                        self.assertNotIn(pr, f.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
