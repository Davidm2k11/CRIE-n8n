"""
In-memory System-Under-Test double (Sprint 9).

Provides deterministic predictions derived from the dataset ground truth so the
real metric functions can be exercised end-to-end without live providers or a
live datastore (accepted deferral per PROJECT_STATUS Known Risks). This is an
adapter DOUBLE, not a placeholder: it returns concrete, controllable outputs so
tests can assert exact metric values (including near-target and below-target
cases). The same harness runs unchanged against live adapters in the target
deployment (provider-agnostic, R-08).
"""
from __future__ import annotations


class AdapterDouble:
    """Configurable double. `quality` in [0,1] scales how closely predictions
    match ground truth, letting tests drive pass and fail scenarios."""

    def __init__(self, dataset: dict, quality: float = 1.0):
        self.dataset = dataset
        self.quality = quality
        self._docs = {d["doc_id"]: d for d in dataset["documents"]}
        self._reqs = {r["req_id"]: r for r in dataset["requirements"]}

    # --- §394 ---------------------------------------------------------------
    def extract_units(self, doc_id: str) -> list[str]:
        expected = self._docs[doc_id]["expected_knowledge_units"]
        keep = max(1, round(len(expected) * self.quality))
        return list(expected[:keep])

    # --- §395 ---------------------------------------------------------------
    def retrieve(self, req_id: str) -> list[str]:
        req = self._reqs[req_id]
        relevant = list(req["relevant_units"])
        if self.quality >= 1.0:
            return relevant + ["KU-9000", "KU-9001"]
        # Degrade: push one relevant item out of top ranks
        distractors = ["KU-9000", "KU-9001", "KU-9002"]
        return distractors[:2] + relevant

    def authority(self, req_id: str) -> str:
        req = self._reqs[req_id]
        if self.quality >= 1.0:
            return req["authority_expected"]
        return "KU-9999"

    # --- §396 ---------------------------------------------------------------
    def citations(self) -> list[dict]:
        good = {
            "correct_document": True, "correct_page": True,
            "correct_section": True, "correct_paragraph": True,
            "correct_evidence": True,
        }
        n = 100
        accurate = round(n * self.quality)
        rows = [dict(good) for _ in range(accurate)]
        rows += [{**good, "correct_page": False} for _ in range(n - accurate)]
        return rows

    # --- §397 ---------------------------------------------------------------
    def responses(self) -> list[dict]:
        total = 1000
        bad = round(total * (1 - self.quality) * 0.5)
        return [{
            "total_statements": total,
            "unsupported_statements": bad,
            "invented_features": 0,
            "invented_citations": 0,
            "missing_evidence": 0,
        }]

    # --- §398 ---------------------------------------------------------------
    def compliance_labels(self):
        n = 100
        agree = round(n * self.quality)
        system = ["Compliant"] * n
        human = ["Compliant"] * agree + ["Non-Compliant"] * (n - agree)
        return system, human

    # --- §400 ---------------------------------------------------------------
    def cost_executions(self) -> list[dict]:
        return [{
            "ocr_cost": 0.10, "embedding_cost": 0.02,
            "reasoning_cost": 0.30, "storage_cost": 0.01,
        } for _ in range(10)]
