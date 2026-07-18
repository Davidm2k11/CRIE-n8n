# All Rights Reserved, Copyright © 2026 Dawod Manasra. Unauthorized copying,
# modification, distribution, or commercial use is prohibited without written
# permission.
#
# CRIE — Compliance Reasoning & Intelligence Engine
# Sprint 6 · Enterprise Reasoning (WF-003)
#
# This package implements the deterministic, platform-owned portions of the
# Enterprise Reasoning Engine per CRIE Enterprise Specification v1.1.1:
#   - SW-022 Prompt Loader        (§262, §173, §175, §176)
#   - SW-023 Enterprise LLM        (§263, R-11: explanation + evidence mapping only)
#   - SW-024 Output Validator      (§264, §90, §298)
#   - complianceLevel derivation   (R-11; §478-481, §480 matrix)
#   - confidence engine            (R-10; §89, §483)
#   - citation re-linking          (R-06; §88, §291)
#   - hallucination detection      (§493)
#   - self-validation              (§494)
#   - human-review triggers        (§91, §491)
#   - single Compliance Result     (R-03; §295)
#
# Sprint isolation: no Sprint 7+ (Output Generation / WF-004) logic is present.

__version__ = "0.7.0"
