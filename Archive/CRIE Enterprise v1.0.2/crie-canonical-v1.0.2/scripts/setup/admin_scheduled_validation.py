#!/usr/bin/env python3
# =====================================================================
# CRIE — scripts/admin_scheduled_validation.py
# Sprint 8 (Administration) · Task S8-9
# Spec: §327 (Configuration Validation), §157 (Prompt Validation),
#       §174 (prompt versioning), §569/§387 (alerting).
#
# Runnable reference implementation of the scheduled validation logic that
# WF-005 invokes (Config Validation node -> UT-000 checks; Prompt Validation
# node -> SW-018 checks). Mirrors the Sprint-1 pattern of shipping the §327
# validation logic as a runnable Python script alongside the n8n JSON.
#
# This validates STRUCTURE against the frozen registries. It does not contact
# live providers (build environment has none). Findings are emitted as Alert
# Center rows (§569) with severity (§387). Non-blocking: on_failure = alert.
#
# All Rights Reserved, Copyright (c) 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
# =====================================================================
from __future__ import annotations
import json
import sys
from dataclasses import dataclass, field, asdict
from typing import Any


# ---- §327 Configuration Validation ----------------------------------
CONFIG_CHECKS = [
    "required_values_exist",   # ✓ Required values exist
    "urls_valid",              # ✓ URLs valid
    "credentials_available",   # ✓ Credentials available (presence only)
    "providers_enabled",       # ✓ Providers enabled
    "models_configured",       # ✓ Models configured
    "feature_flags_valid",     # ✓ Feature Flags valid
]

# ---- §174 Prompt Registry expectations ------------------------------
EXPECTED_PROMPTS = ["PR-001", "PR-002", "PR-003", "PR-004",
                    "PR-005", "PR-006", "PR-007", "PR-008"]
VALID_PROMPT_STATUS = {"active", "deprecated", "draft"}


@dataclass
class Alert:
    alert_type: str
    severity: str          # Info | Warning | Critical  (§387/§569)
    source: str
    message: str
    context: dict = field(default_factory=dict)


def _is_url(v: Any) -> bool:
    return isinstance(v, str) and (v.startswith("http://") or v.startswith("https://"))


def validate_config(config: dict) -> list[Alert]:
    """§327 configuration validation. Returns Alert list (empty == pass)."""
    alerts: list[Alert] = []
    required = config.get("required_values", {})
    for k, v in required.items():
        if v in (None, "", []):
            alerts.append(Alert("ConfigValidationFailure", "Critical", "config",
                                f"Required value missing: {k}", {"key": k}))

    for k, v in config.get("urls", {}).items():
        if not _is_url(v):
            alerts.append(Alert("ConfigValidationFailure", "Warning", "config",
                                f"Invalid URL for {k}", {"key": k, "value": v}))

    # Credentials: presence only, never value (§571 secrets exposed as presence).
    for k, present in config.get("credentials_present", {}).items():
        if not present:
            alerts.append(Alert("ConfigValidationFailure", "Critical", "config",
                                f"Credential not available: {k}", {"key": k}))

    providers = config.get("providers", {})
    if not any(p.get("enabled") for p in providers.values()):
        alerts.append(Alert("ConfigValidationFailure", "Critical", "config",
                            "No providers enabled", {}))
    for name, p in providers.items():
        if p.get("enabled") and not p.get("model"):
            alerts.append(Alert("ConfigValidationFailure", "Warning", "config",
                                f"Enabled provider missing model: {name}", {"provider": name}))

    for flag, val in config.get("feature_flags", {}).items():
        if not isinstance(val, bool):
            alerts.append(Alert("ConfigValidationFailure", "Warning", "config",
                                f"Feature flag not boolean: {flag}", {"flag": flag, "value": val}))
    return alerts


def validate_prompts(registry: list[dict]) -> list[Alert]:
    """§157 prompt validation against the frozen PR-001..PR-008 catalog (§174)."""
    alerts: list[Alert] = []
    present_ids = {p.get("prompt_id") for p in registry}

    for pid in EXPECTED_PROMPTS:
        if pid not in present_ids:
            alerts.append(Alert("PromptValidationFailure", "Critical", "prompt",
                                f"Missing prompt in registry: {pid}", {"prompt_id": pid}))

    for p in registry:
        pid = p.get("prompt_id")
        if pid not in EXPECTED_PROMPTS:
            alerts.append(Alert("PromptValidationFailure", "Warning", "prompt",
                                f"Unknown prompt id (not in PR-001..PR-008): {pid}",
                                {"prompt_id": pid}))
        if not p.get("version"):
            alerts.append(Alert("PromptValidationFailure", "Warning", "prompt",
                                f"Prompt not versioned (§174): {pid}", {"prompt_id": pid}))
        status = (p.get("status") or "").lower()
        if status not in VALID_PROMPT_STATUS:
            alerts.append(Alert("PromptValidationFailure", "Warning", "prompt",
                                f"Invalid prompt status: {pid} -> {status}", {"prompt_id": pid}))
    return alerts


def run(config: dict, registry: list[dict]) -> dict:
    alerts = validate_config(config) + validate_prompts(registry)
    return {
        "passed": len(alerts) == 0,
        "checks_run": {"config": CONFIG_CHECKS, "prompts_expected": EXPECTED_PROMPTS},
        "alerts": [asdict(a) for a in alerts],
    }


def _demo() -> dict:
    """Self-contained valid fixture -> expected PASS."""
    config = {
        "required_values": {"environment": "prod", "config_version": "1.1.1"},
        "urls": {"supabase_url": "https://example.supabase.co"},
        "credentials_present": {"supabase_service_key": True, "llm_api_key": True},
        "providers": {
            "openai": {"enabled": True, "model": "gpt-x"},
            "claude": {"enabled": True, "model": "claude-x"},
            "azure_ocr": {"enabled": True, "model": "prebuilt-layout"},
        },
        "feature_flags": {"reranker_enabled": False, "queue_mode": True},
    }
    registry = [{"prompt_id": p, "version": "1.0.0", "status": "active"} for p in EXPECTED_PROMPTS]
    return run(config, registry)


if __name__ == "__main__":
    result = _demo()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["passed"] else 1)
