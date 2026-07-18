"""
CRIE Benchmark Evaluator (Sprint 9, S9-3/S9-8).

Takes measured metric values and the loaded config, and produces evaluation
rows in the exact shape of monitoring.benchmark_results (migration 0027). The
pass/fail decision uses ONLY the config target (R-08) and the frozen §196
direction — no target is hardcoded here. Latency evaluation uses §197 targets.

Also produces the §405 Acceptance Criteria Matrix and the §406 benchmark gate
in-memory (the SQL views compute the same from persisted rows; this mirror
lets tests assert parity without a live database).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


# Module -> benchmark family mapping (§405), identical to migration 0028's
# admin.v_acceptance_criteria_matrix module_map. Kept in one place per module.
MODULE_BENCHMARK_MAP = [
    ("Platform Foundation", "latency"),
    ("Knowledge Ingestion", "knowledge_extraction"),
    ("Repository", "knowledge_extraction"),
    ("Retrieval", "retrieval"),
    ("Reasoning", "hallucination"),
    ("Reasoning", "compliance_accuracy"),
    ("Output", "citation"),
    ("Administration", "cost"),
]


def _passes(value: float, target: float, higher_is_better: bool) -> bool:
    return value >= target if higher_is_better else value <= target


def evaluate_benchmarks(
    measured: dict[str, dict[str, float]],
    config: dict[str, Any],
    run_id: str | None = None,
) -> list[dict]:
    """Build benchmark_results rows from measured metric dicts.

    `measured` maps family -> {metric_name: value, ...}.
    Returns one row per gated metric (with pass/fail) and one row per reported
    metric (target NULL). Row keys match migration 0027 columns.
    """
    run_id = run_id or str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []

    for family, spec in config["benchmarks"].items():
        family_measured = measured.get(family, {})
        gated_metric = spec.get("gated_metric")
        target = spec.get("target")
        hib = spec.get("higher_is_better")
        spec_ref = spec["spec_ref"]

        for metric, value in family_measured.items():
            is_gated = (metric == gated_metric and target is not None)
            passed = (_passes(value, target, hib) if is_gated else None)
            rows.append({
                "run_id": run_id,
                "run_started_at": started,
                "benchmark": family,
                "metric": metric,
                "metric_value": value,
                "target_value": target if is_gated else None,
                "higher_is_better": hib if is_gated else None,
                "passed": passed,
                "spec_ref": spec_ref,
                "difficulty": None,
                "dataset_category": None,
                "notes": None,
            })
    return rows


def evaluate_latency(
    measured_seconds: dict[str, float],
    config: dict[str, Any],
    run_id: str | None = None,
) -> list[dict]:
    """Build latency_history rows from measured per-stage durations (§197/§399)."""
    run_id = run_id or str(uuid.uuid4())
    targets = config["latency"]["stage_targets_seconds"]
    rows: list[dict] = []
    for stage, duration in measured_seconds.items():
        target = targets.get(stage)
        passed = (duration <= target) if target is not None else None
        rows.append({
            "run_id": run_id,
            "stage": stage,
            "duration_seconds": duration,
            "target_seconds": target,
            "passed": passed,
            "document_count": None,
        })
    return rows


def acceptance_matrix(
    benchmark_rows: list[dict],
    latency_rows: list[dict] | None = None,
    operational_validation: dict[str, bool] | None = None,
) -> dict[str, str]:
    """Compute §405 matrix (mirror of SQL admin.v_acceptance_criteria_matrix).

    A module Passes iff every gated signal mapped to it passed:
      * benchmark families with a §194-400 numeric target -> gated benchmark row
      * latency (§197/§399) -> Platform Foundation, gated per-stage
      * modules whose §405 quality is validated operationally rather than by a
        §394-400 numeric benchmark (Administration: cost is REPORTED per §400,
        not numerically gated) pass on `operational_validation` supplied by the
        run (§199/§390). No numeric target is fabricated for these — doing so
        would violate "numbers unchanged from spec" (S9 DoD).

    'No Data' when a required signal is absent for the run.
    """
    latency_rows = latency_rows or []
    operational_validation = operational_validation or {}

    gated_by_family: dict[str, list[bool]] = {}
    for r in benchmark_rows:
        if r["target_value"] is not None and r["passed"] is not None:
            gated_by_family.setdefault(r["benchmark"], []).append(r["passed"])

    # Latency (§197): a stage counts only when it has a target.
    latency_passes = [r["passed"] for r in latency_rows if r["passed"] is not None]
    if latency_passes:
        gated_by_family["latency"] = latency_passes

    # Families that are reported-only per spec (no numeric gate). These modules
    # are validated operationally (§199/§390), never by a fabricated number.
    OPERATIONAL_FAMILIES = {"cost"}

    result: dict[str, str] = {}
    for module, family in MODULE_BENCHMARK_MAP:
        if family in OPERATIONAL_FAMILIES:
            flag = operational_validation.get(module)
            if flag is None:
                outcome = "No Data"
            else:
                outcome = "Pass" if flag else "Fail"
        else:
            results = gated_by_family.get(family)
            if not results:
                outcome = "No Data"
            elif all(results):
                outcome = "Pass"
            else:
                outcome = "Fail"
        # A module may map to multiple families (Reasoning); Fail dominates,
        # then No Data, then Pass.
        prior = result.get(module)
        result[module] = _combine(prior, outcome)
    return result


def _combine(prior: str | None, new: str) -> str:
    order = {"Fail": 0, "No Data": 1, "Pass": 2}
    if prior is None:
        return new
    return prior if order[prior] <= order[new] else new


def benchmark_gate(
    benchmark_rows: list[dict],
    latency_rows: list[dict] | None = None,
    operational_validation: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Compute the §406 benchmark portion of the readiness gate.

    'All benchmark targets met' (§406 ✓1) covers both the §394-400 numeric
    benchmarks and the §197 latency targets.
    """
    latency_rows = latency_rows or []
    gated = [r["passed"] for r in benchmark_rows
             if r["target_value"] is not None and r["passed"] is not None]
    gated += [r["passed"] for r in latency_rows if r["passed"] is not None]
    all_met = all(gated) if gated else None
    matrix = acceptance_matrix(benchmark_rows, latency_rows, operational_validation)
    matrix_vals = set(matrix.values())
    if "Fail" in matrix_vals:
        matrix_pass = False
    elif "No Data" in matrix_vals:
        matrix_pass = None
    else:
        matrix_pass = True

    if all_met is True and matrix_pass is True:
        status = "Benchmark gate: PASS (deployment sign-offs pending)"
    elif all_met is False or matrix_pass is False:
        status = "Benchmark gate: FAIL — do not deploy"
    else:
        status = "Benchmark gate: NO DATA"

    return {
        "all_benchmark_targets_met": all_met,
        "acceptance_matrix_pass": matrix_pass,
        "gate_status": status,
    }
