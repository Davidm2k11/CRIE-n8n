"""
CRIE Benchmark Runner (Sprint 9, S9-3/S9-8).

Orchestrates a benchmark run:
  1. Loads + validates config (R-08).
  2. Loads the labeled dataset (§392/§393).
  3. Computes metrics via metrics.py against a supplied "system output" — in
     the build environment this is an in-memory adapter double that returns
     deterministic results derived from the ground truth (real evaluation
     logic exercised end-to-end; live providers deferred to integration stage).
  4. Evaluates pass/fail vs frozen targets (evaluate.py).
  5. Emits SQL INSERT statements for monitoring.benchmark_results and
     monitoring.latency_history (migration 0027), and a Benchmark Report.

This module contains NO placeholder scoring — every metric is computed by the
real functions in metrics.py. The adapter double stands in only for the live
datastore/providers (accepted deferral, PROJECT_STATUS Known Risks).
"""
from __future__ import annotations

import json
import os
import uuid

from config_loader import load_config
import metrics
import evaluate


def _dataset_path() -> str:
    # Canonical layout (§631): labeled dataset lives in the repo-root
    # `benchmark/datasets/` folder. This module sits at scripts/benchmark/, so
    # the repo root is two levels up.
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "benchmark",
                                         "datasets", "benchmark_dataset.json"))


def load_dataset(path: str | None = None) -> dict:
    path = path or _dataset_path()
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def measure(dataset: dict, system) -> dict[str, dict[str, float]]:
    """Compute all §394-400 metrics from `system` output over the dataset.

    `system` is any object implementing the SystemUnderTest protocol. Metrics
    are real; only the source of predictions is abstracted.
    """
    # --- §394 Knowledge Extraction (aggregate over documents) --------------
    ke_p, ke_r, ke_f1, n = 0.0, 0.0, 0.0, 0
    for doc in dataset["documents"]:
        extracted = set(system.extract_units(doc["doc_id"]))
        expected = set(doc["expected_knowledge_units"])
        m = metrics.precision_recall_f1(extracted, expected)
        ke_p += m["precision"]; ke_r += m["recall"]; ke_f1 += m["f1"]; n += 1
    ke = {"precision": ke_p / n, "recall": ke_r / n, "f1": ke_f1 / n}

    # --- §395 Retrieval (aggregate over requirements) ----------------------
    r5 = r10 = mrr = ndcg = auth = 0.0
    reqs = dataset["requirements"]
    pred_auth, exp_auth = [], []
    for req in reqs:
        ranked = system.retrieve(req["req_id"])
        relevant = set(req["relevant_units"])
        r5 += metrics.recall_at_k(ranked, relevant, 5)
        r10 += metrics.recall_at_k(ranked, relevant, 10)
        mrr += metrics.mean_reciprocal_rank(ranked, relevant)
        graded = {u: 1.0 for u in relevant}
        ndcg += metrics.ndcg_at_k(ranked, graded, 10)
        pred_auth.append(system.authority(req["req_id"]))
        exp_auth.append(req["authority_expected"])
    k = len(reqs)
    retrieval = {
        "recall_at_5": r5 / k, "recall_at_10": r10 / k,
        "mrr": mrr / k, "ndcg": ndcg / k,
        "authority_accuracy": metrics.authority_accuracy(pred_auth, exp_auth),
    }

    # --- §396 Citation -----------------------------------------------------
    citation = metrics.citation_accuracy(system.citations())

    # --- §397 Hallucination ------------------------------------------------
    hallucination = metrics.hallucination_rate(system.responses())

    # --- §398 Compliance Accuracy ------------------------------------------
    sys_labels, human_labels = system.compliance_labels()
    compliance = metrics.human_agreement(sys_labels, human_labels)

    # --- §400 Cost ---------------------------------------------------------
    cost = metrics.cost_aggregate(
        system.cost_executions(),
        requirement_count=len(reqs),
        document_count=len(dataset["documents"]),
    )

    return {
        "knowledge_extraction": ke,
        "retrieval": retrieval,
        "citation": citation,
        "hallucination": hallucination,
        "compliance_accuracy": compliance,
        "cost": cost,
    }


def _sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def emit_sql(benchmark_rows: list[dict], latency_rows: list[dict]) -> str:
    lines = ["-- Sprint 9 benchmark run inserts (monitoring.* per 0027)"]
    for r in benchmark_rows:
        lines.append(
            "INSERT INTO monitoring.benchmark_results "
            "(run_id, benchmark, metric, metric_value, target_value, "
            "higher_is_better, passed, spec_ref, difficulty, dataset_category, notes) "
            "VALUES ("
            f"{_sql_literal(r['run_id'])}, {_sql_literal(r['benchmark'])}, "
            f"{_sql_literal(r['metric'])}, {_sql_literal(r['metric_value'])}, "
            f"{_sql_literal(r['target_value'])}, {_sql_literal(r['higher_is_better'])}, "
            f"{_sql_literal(r['passed'])}, {_sql_literal(r['spec_ref'])}, "
            f"{_sql_literal(r['difficulty'])}, {_sql_literal(r['dataset_category'])}, "
            f"{_sql_literal(r['notes'])});"
        )
    for r in latency_rows:
        lines.append(
            "INSERT INTO monitoring.latency_history "
            "(run_id, stage, duration_seconds, target_seconds, passed, document_count) "
            "VALUES ("
            f"{_sql_literal(r['run_id'])}, {_sql_literal(r['stage'])}, "
            f"{_sql_literal(r['duration_seconds'])}, {_sql_literal(r['target_seconds'])}, "
            f"{_sql_literal(r['passed'])}, {_sql_literal(r['document_count'])});"
        )
    return "\n".join(lines) + "\n"


def run(system, latency_measurements: dict[str, float],
        config_path: str | None = None,
        dataset_path: str | None = None,
        operational_validation: dict[str, bool] | None = None) -> dict:
    """Full run. Returns dict with rows, matrix, gate, and report text.

    `operational_validation` supplies pass/fail for §405 modules whose quality
    is validated operationally rather than by a §394-400 numeric benchmark
    (e.g. Administration/cost, which §400 reports but does not numerically
    gate). Omit to leave those modules as 'No Data'.
    """
    config = load_config(config_path)
    dataset = load_dataset(dataset_path)
    run_id = str(uuid.uuid4())

    measured = measure(dataset, system)
    bench_rows = evaluate.evaluate_benchmarks(measured, config, run_id)
    lat_rows = evaluate.evaluate_latency(latency_measurements, config, run_id)
    matrix = evaluate.acceptance_matrix(bench_rows, lat_rows, operational_validation)
    gate = evaluate.benchmark_gate(bench_rows, lat_rows, operational_validation)

    return {
        "run_id": run_id,
        "measured": measured,
        "benchmark_rows": bench_rows,
        "latency_rows": lat_rows,
        "acceptance_matrix": matrix,
        "gate": gate,
        "sql": emit_sql(bench_rows, lat_rows),
    }
