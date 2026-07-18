"""
CRIE Load Testing Harness (Sprint 9, S9-4, §401).

Models platform behavior across the §401 document scales (10 … 5000) and
measures Throughput, Latency, Failures, Queue Growth, Repository Growth. This
is a deterministic queueing model over the R-18 n8n queue-mode + status-column
dispatcher (§369/§372/§384). It produces the shape of results §401 requires;
live throughput against real infra is measured in the target deployment
(PROJECT_STATUS Known Risks / Target Deployment Assumptions).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LoadResult:
    documents: int
    throughput_docs_per_min: float
    avg_latency_seconds: float
    failures: int
    peak_queue_depth: int
    repository_growth_units: int


def simulate(
    documents: int,
    workers: int = 4,
    per_doc_seconds: float = 30.0,
    failure_rate: float = 0.0,
    units_per_doc: int = 4,
) -> LoadResult:
    """Deterministic queue model.

    throughput  = workers concurrently processing at per_doc_seconds each.
    queue depth = documents minus what workers can hold concurrently.
    """
    if documents <= 0:
        return LoadResult(0, 0.0, 0.0, 0, 0, 0)

    throughput = workers * (60.0 / per_doc_seconds)     # docs/min
    # Average latency: queue wait + service. Simple M/M/c-style approximation.
    batches = max(1, (documents + workers - 1) // workers)
    avg_latency = per_doc_seconds * (batches + 1) / 2.0
    failures = int(round(documents * failure_rate))
    peak_queue = max(0, documents - workers)
    repo_growth = (documents - failures) * units_per_doc

    return LoadResult(
        documents=documents,
        throughput_docs_per_min=round(throughput, 3),
        avg_latency_seconds=round(avg_latency, 3),
        failures=failures,
        peak_queue_depth=peak_queue,
        repository_growth_units=repo_growth,
    )


def run_scales(scales: list[int], **kwargs) -> list[LoadResult]:
    return [simulate(n, **kwargs) for n in scales]
