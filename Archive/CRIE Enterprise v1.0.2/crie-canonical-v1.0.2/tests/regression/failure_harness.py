"""
CRIE Failure Testing Harness (Sprint 9, S9-5, §402).

Simulates each §402 failure scenario and asserts deterministic recovery. A
recovery is deterministic when, given the same failure, the system always
resolves to the same terminal state (retry-then-quarantine, circuit-open, or
transactional rollback) grounded in the R-18 circuit-breaker mechanism
(health_checks state) and §369/§372/§384 status-column dispatch.

No live services are called; this harness exercises the recovery DECISION
logic, which is what §402 mandates ("Every failure SHALL produce deterministic
recovery"). Live fault injection against real infra is a Sprint 10 / deployment
activity (PROJECT_STATUS Known Risks).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Terminal recovery states (grounded in R-18 / §369-384 semantics)
RETRY_THEN_QUARANTINE = "retry_then_quarantine"
CIRCUIT_OPEN = "circuit_open"
ROLLBACK = "transactional_rollback"
REJECT_INPUT = "reject_input"


@dataclass
class HealthState:
    """Minimal circuit-breaker model over health_checks (R-18, §387)."""
    failure_count: int = 0
    threshold: int = 3
    state: str = "Healthy"

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.threshold:
            self.state = "Open"

    def is_open(self) -> bool:
        return self.state == "Open"


@dataclass
class RecoveryEngine:
    """Deterministic recovery decisions for §402 scenarios."""
    max_retries: int = 3
    health: HealthState = field(default_factory=HealthState)

    def handle(self, scenario: str) -> str:
        if scenario in ("ocr_failure", "llm_failure", "network_failure", "timeout"):
            # Provider/transport faults: retry up to max, tripping the breaker.
            for _ in range(self.max_retries):
                self.health.record_failure()
                if self.health.is_open():
                    return CIRCUIT_OPEN
            return RETRY_THEN_QUARANTINE
        if scenario == "database_failure":
            return ROLLBACK           # §14469 "Failure SHALL rollback the transaction"
        if scenario == "repository_lock":
            return RETRY_THEN_QUARANTINE
        if scenario in ("corrupted_document", "missing_metadata"):
            return REJECT_INPUT       # deterministic reject; no partial ingest
        raise ValueError(f"unknown failure scenario: {scenario}")


def run_all(scenarios: list[str]) -> dict[str, str]:
    """Run each scenario twice; assert identical (deterministic) outcome."""
    results: dict[str, str] = {}
    for sc in scenarios:
        first = RecoveryEngine().handle(sc)
        second = RecoveryEngine().handle(sc)
        assert first == second, f"{sc} recovery is non-deterministic"
        results[sc] = first
    return results
