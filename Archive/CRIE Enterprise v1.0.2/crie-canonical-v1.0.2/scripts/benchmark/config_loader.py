"""
CRIE Benchmark Config Loader (Sprint 9).

Loads and validates config/benchmark.config.yaml at startup (R-08; validation
pattern per §327/§157). Fails fast on missing/invalid target definitions so no
benchmark runs against an unvalidated target set. No target values are defaulted
in code — the config is authoritative.
"""
from __future__ import annotations

import os
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


REQUIRED_BENCHMARK_KEYS = {"spec_ref", "report_metrics"}
GATED_FAMILIES = {
    "knowledge_extraction", "retrieval", "citation",
    "hallucination", "compliance_accuracy",
}


class ConfigError(ValueError):
    """Raised when benchmark config fails startup validation."""


def _default_path() -> str:
    # Canonical layout (§627): configuration YAML lives in the repo-root
    # `configuration/` folder. This module sits at scripts/benchmark/, so the
    # repo root is two levels up.
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "configuration",
                                         "benchmark.yaml"))


def load_config(path: str | None = None) -> dict[str, Any]:
    """Load and validate the benchmark config. Raises ConfigError on problems."""
    if yaml is None:  # pragma: no cover
        raise ConfigError("PyYAML is required to load benchmark config")

    path = path or _default_path()
    if not os.path.exists(path):
        raise ConfigError(f"benchmark config not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    _validate(cfg)
    return cfg


def _validate(cfg: dict[str, Any]) -> None:
    if not isinstance(cfg, dict):
        raise ConfigError("config root must be a mapping")

    for key in ("version", "spec_version", "benchmarks", "latency"):
        if key not in cfg:
            raise ConfigError(f"missing top-level key: {key}")

    benchmarks = cfg["benchmarks"]
    if not isinstance(benchmarks, dict) or not benchmarks:
        raise ConfigError("benchmarks must be a non-empty mapping")

    for family, spec in benchmarks.items():
        missing = REQUIRED_BENCHMARK_KEYS - set(spec)
        if missing:
            raise ConfigError(f"benchmark '{family}' missing keys: {missing}")

        if family in GATED_FAMILIES:
            if not spec.get("gated_metric"):
                raise ConfigError(
                    f"gated benchmark '{family}' must define gated_metric")
            if "target" not in spec:
                raise ConfigError(
                    f"gated benchmark '{family}' must define target")
            if not isinstance(spec.get("higher_is_better"), bool):
                raise ConfigError(
                    f"benchmark '{family}' must set higher_is_better bool")
            target = spec["target"]
            if not isinstance(target, (int, float)):
                raise ConfigError(
                    f"benchmark '{family}' target must be numeric")
            if not (0 <= float(target) <= 1):
                raise ConfigError(
                    f"benchmark '{family}' target must be a rate in [0,1]")

    latency = cfg["latency"]
    if "stage_targets_seconds" not in latency:
        raise ConfigError("latency.stage_targets_seconds is required")
    for stage, tgt in latency["stage_targets_seconds"].items():
        if tgt is not None and (not isinstance(tgt, (int, float)) or tgt <= 0):
            raise ConfigError(
                f"latency target for '{stage}' must be positive or null")
