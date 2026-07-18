#!/usr/bin/env python3
"""validate_configuration.py — CRIE Startup Validation core (R-14, §326-327).

Loads the authored configuration YAML set (§627, the source of truth, R-08),
merges it into the runtime configuration object, and runs the §327 validation
checks. This is the same validation the UT-007_Startup_Validation n8n Code node
performs; it is factored out here so the check is runnable and testable in CI
before the n8n runtime and the configuration.* cache tables (Sprint 2) exist.

Exit 0 => configuration valid (health would be Healthy).
Exit 1 => configuration invalid (health would be Critical + alert).

Secret VALUES are never read or printed — only presence of required env vars is
checked, and only when --check-env is passed (deploy-time). By default env is
not required so the check runs in a clean CI/dev checkout.
"""
import argparse
import glob
import json
import os
import sys
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CONFIG_DIR = os.path.join(ROOT, "configuration")

REQUIRED_ENV = [                       # §314, §322
    "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
    "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "AZURE_DOCUMENT_INTELLIGENCE_KEY",
    "OPENAI_API_KEY",
]


def load_config():
    import yaml
    merged = {}
    # Files whose keys ARE the domain names (not a single wrapping domain key).
    # providers.yaml carries ocr/llm/embedding/storage at its root; its keys are
    # merged as-is. Every other per-domain file either (a) wraps its content
    # under a top-level key equal to its filename stem (storage.yaml ->
    # {storage: {...}}), or (b) authors its keys unwrapped at the root
    # (retrieval.yaml -> {topK: ..., ...}). Case (b) is namespaced under the
    # filename stem so callers resolve it as <stem>.<key>, matching the wrapped
    # convention and the R-14 validator's dotted lookups (§327). This reads the
    # authored YAML unchanged — no file is mutated.
    MULTI_DOMAIN = {"providers", "authority"}
    for path in sorted(glob.glob(os.path.join(CONFIG_DIR, "*.yaml"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            continue
        if stem in MULTI_DOMAIN:
            for k, v in data.items():
                merged[k] = v
        elif list(data.keys()) == [stem]:
            # already wrapped under its own stem
            merged[stem] = data[stem]
        elif stem in data and isinstance(data[stem], dict) and len(data) == 1:
            merged[stem] = data[stem]
        else:
            # unwrapped domain file: namespace root keys under the stem, but
            # drop a redundant schemaVersion so it does not shadow anything.
            body = {k: v for k, v in data.items() if k != "schemaVersion"}
            merged.setdefault(stem, {})
            if isinstance(merged[stem], dict):
                merged[stem].update(body)
            else:
                merged[stem] = body
    return merged


def get(cfg, dotted):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def validate(cfg, check_env=False):
    errors = []

    # 1. Required config values exist (§327).
    required_keys = [
        "ocr.provider", "ocr.model", "ocr.endpoint", "ocr.timeout", "ocr.retryCount",
        "llm.provider", "llm.model", "llm.maxTokens", "llm.timeout",
        "embedding.provider", "embedding.model", "embedding.dimensions", "embedding.batchSize",
        "storage.provider",
        "repository.certificationRequired", "repository.transactionTimeout",
        "retrieval.topK", "retrieval.minimumSimilarity", "retrieval.rerankerEnabled",
        "retrieval.maximumContextTokens",
        "monitoring.telemetryEnabled", "monitoring.healthCheckInterval",
        "logging.logLevel", "logging.structuredLogging",
    ]
    for k in required_keys:
        if get(cfg, k) in (None, ""):
            errors.append(f"missing_config:{k}")

    # 2. Embedding dimension locked at 1536 for v1 (R-09).
    dims = get(cfg, "embedding.dimensions")
    if dims is not None and int(dims) != 1536:
        errors.append("embedding.dimensions_must_be_1536")

    # 3. logLevel is a valid enum (§15).
    lvl = get(cfg, "logging.logLevel")
    if lvl is not None and lvl not in ("INFO", "WARNING", "ERROR", "CRITICAL"):
        errors.append(f"invalid_log_level:{lvl}")

    # 4. structuredLogging must be true (§15 — free-text logging prohibited).
    if get(cfg, "logging.structuredLogging") is not True:
        errors.append("structured_logging_must_be_true")

    # 5. Feature flags valid: booleans only, default false (§312).
    flags = get(cfg, "featureFlags") or {}
    for k, v in flags.items():
        if not isinstance(v, bool):
            errors.append(f"feature_flag_not_boolean:{k}")

    # 6. Reranker gate (§305, R-12).
    if get(cfg, "retrieval.rerankerEnabled") is True and not get(cfg, "retrieval.crossEncoderModel"):
        errors.append("reranker_enabled_without_model")

    # 7. Ranking weights (§462) sum to 1.0 when present.
    r = get(cfg, "ranking")
    if isinstance(r, dict):
        s = sum(float(r.get(w, 0)) for w in ("semanticWeight", "keywordWeight", "authorityWeight"))
        if abs(s - 1.0) > 1e-6:
            errors.append(f"ranking_weights_sum_not_1.0:{s}")

    # 7a. Vector index config is valid (§227) — user-adjustable, so startup-validated.
    vi = get(cfg, "embedding.vectorIndex")
    if isinstance(vi, dict):
        if vi.get("type") not in ("hnsw", "ivfflat"):
            errors.append(f"invalid_vector_index_type:{vi.get('type')}")
        if vi.get("metric") not in ("cosine", "l2", "ip"):
            errors.append(f"invalid_vector_index_metric:{vi.get('metric')}")

    # 7b. Authority-source model present with the 9 canonical sources (§439, R-16).
    auth = get(cfg, "authoritySources")
    if not isinstance(auth, list) or len(auth) != 9:
        errors.append("authority_sources_must_have_9_entries")
    else:
        for a in auth:
            if "source" not in a or "score" not in a:
                errors.append("authority_source_missing_fields"); break

    # 8. URL validity (§327) for config-declared endpoints (env-independent form).
    ep = get(cfg, "ocr.endpoint")
    if ep and not ep.startswith("${"):    # skip unresolved env placeholders
        p = urlparse(ep)
        if not (p.scheme and p.netloc):
            errors.append("invalid_ocr_endpoint")

    # 9. Deploy-time only: required env secrets present (§314). Presence only.
    if check_env:
        for k in REQUIRED_ENV:
            if not os.environ.get(k, "").strip():
                errors.append(f"missing_env:{k}")

    # 7c. Knowledge category reference has the 16 frozen values (§438, R-05).
    import yaml as _yaml
    cat_path = os.path.join(ROOT, "database", "seeds", "knowledge_categories.yaml")
    if os.path.exists(cat_path):
        cats = (_yaml.safe_load(open(cat_path)) or {}).get("categories") or []
        if len(cats) != 16:
            errors.append(f"knowledge_categories_must_be_16:{len(cats)}")

    valid = len(errors) == 0
    state = "Healthy" if valid else "Critical"
    health = {
        "repository": state, "ocr": state, "llm": state,
        "embeddingProvider": state, "storage": state, "database": state,
        "n8n": "Healthy", "overall": state,
    }
    return {
        "valid": valid,
        "errors": errors,
        "health": health,
        "alert": None if valid else {"severity": "Critical", "reason": "startup_validation_failed", "errors": errors},
        "blockExecution": not valid,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-env", action="store_true", help="also require deploy-time env secrets (§314)")
    ap.add_argument("--json", action="store_true", help="emit the health/validation report as JSON")
    args = ap.parse_args()

    cfg = load_config()
    result = validate(cfg, check_env=args.check_env)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Startup Validation: {'PASS' if result['valid'] else 'FAIL'} "
              f"(health.overall = {result['health']['overall']})")
        for e in result["errors"]:
            print(f"  ✗ {e}")
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
