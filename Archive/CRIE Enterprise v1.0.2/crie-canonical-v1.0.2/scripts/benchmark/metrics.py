"""
CRIE Benchmark Metrics (Sprint 9, S9-3).

Real metric computations for the §394-400 benchmark families. Pure functions,
no I/O, no provider calls — deterministic and unit-tested (S9-1). Targets are
NOT embedded here; the evaluator (evaluate.py) reads them from
config/benchmark.config.yaml (R-08).

Spec references:
  §394 Knowledge Extraction : precision, recall, F1
  §395 Retrieval            : Recall@k, MRR, NDCG, authority accuracy
  §396 Citation             : citation accuracy, broken/missing rates
  §397 Hallucination        : hallucination rate, unsupported claims
  §398 Compliance Accuracy  : human agreement
  §400 Cost                 : cost aggregation
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence


# --------------------------------------------------------------------------- #
# §394 Knowledge Extraction
# --------------------------------------------------------------------------- #
def precision_recall_f1(
    extracted: set,
    expected: set,
) -> dict:
    """Set-based precision/recall/F1 over knowledge-unit identifiers (§394).

    precision = TP / (TP + FP), recall = TP / (TP + FN),
    F1 = harmonic mean. Empty-denominator cases return 0.0 (no credit).
    """
    tp = len(extracted & expected)
    fp = len(extracted - expected)
    fn = len(expected - extracted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "duplicate_rate": 0.0,   # populated by caller when dup detection runs
        "missing_units": fn,
    }


# --------------------------------------------------------------------------- #
# §395 Retrieval
# --------------------------------------------------------------------------- #
def recall_at_k(ranked: Sequence, relevant: set, k: int) -> float:
    """Fraction of relevant items appearing in the top-k of `ranked` (§395)."""
    if not relevant:
        return 0.0
    topk = set(ranked[:k])
    return len(topk & relevant) / len(relevant)


def mean_reciprocal_rank(ranked: Sequence, relevant: set) -> float:
    """Reciprocal rank of the first relevant item (§395). 0.0 if none found."""
    for idx, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(ranked: Sequence, relevance: dict, k: int) -> float:
    """Normalized DCG@k with graded relevance (§395).

    `relevance` maps item -> gain (>=0). DCG uses log2(rank+1) discount.
    Returns 0.0 when ideal DCG is 0.
    """
    def dcg(items: Sequence) -> float:
        total = 0.0
        for idx, item in enumerate(items[:k], start=1):
            gain = relevance.get(item, 0.0)
            total += gain / math.log2(idx + 1)
        return total

    actual = dcg(ranked)
    ideal_order = sorted(relevance, key=lambda i: relevance[i], reverse=True)
    ideal = dcg(ideal_order)
    return actual / ideal if ideal else 0.0


def authority_accuracy(predicted: Iterable, expected: Iterable) -> float:
    """Fraction of items whose predicted authority source matches expected."""
    pred = list(predicted)
    exp = list(expected)
    if not exp:
        return 0.0
    matches = sum(1 for p, e in zip(pred, exp) if p == e)
    return matches / len(exp)


# --------------------------------------------------------------------------- #
# §396 Citation
# --------------------------------------------------------------------------- #
def citation_accuracy(citations: Sequence[dict]) -> dict:
    """Validate citations against the 5 §396 checks.

    Each citation dict carries booleans:
      correct_document, correct_page, correct_section,
      correct_paragraph, correct_evidence
    A citation is accurate only if ALL five checks pass.
    broken   = wrong document/page/section/paragraph.
    missing  = citation flagged with `missing=True`.
    """
    if not citations:
        return {"citation_accuracy": 0.0,
                "broken_citation_rate": 0.0,
                "missing_citation_rate": 0.0}

    checks = ("correct_document", "correct_page", "correct_section",
              "correct_paragraph", "correct_evidence")
    total = len(citations)
    accurate = 0
    broken = 0
    missing = 0
    for c in citations:
        if c.get("missing"):
            missing += 1
            continue
        if all(c.get(chk, False) for chk in checks):
            accurate += 1
        else:
            broken += 1

    return {
        "citation_accuracy": accurate / total,
        "broken_citation_rate": broken / total,
        "missing_citation_rate": missing / total,
    }


# --------------------------------------------------------------------------- #
# §397 Hallucination
# --------------------------------------------------------------------------- #
def hallucination_rate(responses: Sequence[dict]) -> dict:
    """Hallucination rate over generated responses (§397).

    Each response dict carries integer counts:
      total_statements, unsupported_statements, invented_features,
      invented_citations, missing_evidence
    hallucination_rate = sum(unsupported + invented*) / sum(total_statements).
    """
    total_stmts = sum(r.get("total_statements", 0) for r in responses)
    if total_stmts == 0:
        return {"hallucination_rate": 0.0,
                "unsupported_claims": 0,
                "invented_citations": 0}

    unsupported = sum(r.get("unsupported_statements", 0) for r in responses)
    inv_feat = sum(r.get("invented_features", 0) for r in responses)
    inv_cite = sum(r.get("invented_citations", 0) for r in responses)

    hallucinated = unsupported + inv_feat + inv_cite
    return {
        "hallucination_rate": hallucinated / total_stmts,
        "unsupported_claims": unsupported,
        "invented_citations": inv_cite,
    }


# --------------------------------------------------------------------------- #
# §398 Compliance Accuracy
# --------------------------------------------------------------------------- #
def human_agreement(system_labels: Sequence, human_labels: Sequence) -> dict:
    """Agreement fraction between system and human expert labels (§398)."""
    if not human_labels or len(system_labels) != len(human_labels):
        return {"human_agreement": 0.0}
    agree = sum(1 for s, h in zip(system_labels, human_labels) if s == h)
    return {"human_agreement": agree / len(human_labels)}


# --------------------------------------------------------------------------- #
# §400 Cost
# --------------------------------------------------------------------------- #
def cost_aggregate(
    executions: Sequence[dict],
    requirement_count: int,
    document_count: int,
    days_measured: int = 30,
) -> dict:
    """Aggregate per-execution costs into §400 cost benchmark fields."""
    def s(field: str) -> float:
        return sum(e.get(field, 0.0) for e in executions)

    ocr = s("ocr_cost")
    emb = s("embedding_cost")
    llm = s("reasoning_cost")
    storage = s("storage_cost")
    total = ocr + emb + llm + storage

    per_req = total / requirement_count if requirement_count else 0.0
    per_doc = total / document_count if document_count else 0.0
    monthly = (total / days_measured) * 30 if days_measured else 0.0

    return {
        "ocr_cost": ocr,
        "embedding_cost": emb,
        "reasoning_cost": llm,
        "storage_cost": storage,
        "avg_cost_per_requirement": per_req,
        "avg_cost_per_document": per_doc,
        "monthly_projection": monthly,
    }
