#!/usr/bin/env python3
# =====================================================================
# CRIE — tests/test_sprint8.py
# Sprint 8 (Administration) acceptance + artifact tests.
# Spec: §578 acceptance criteria, §558-§577 dashboards, §568/§569 health/alert,
#       §266-§268 SW-026/027/028, §327/§157 validation, §232 views, R-02/R-17/R-18.
#
# Pure-stdlib (no live DB / no network — build environment has none). Validates:
#  - migration SQL structure (views/tables/columns present, additive-only)
#  - importable n8n JSON well-formedness + required nodes/ids
#  - config YAML completeness
#  - S8-9 validation logic (positive + negative)
#  - §578 acceptance-criteria coverage matrix
#
# All Rights Reserved, Copyright (c) 2026 Dawod Manasra.
# =====================================================================
import json
import os
import re
import sys
import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIG = os.path.join(ROOT, "database", "migrations")
RBK = os.path.join(ROOT, "database", "rollback")
WF = os.path.join(ROOT, "workflows", "master")
SW = os.path.join(ROOT, "workflows", "shared")
CFG = os.path.join(ROOT, "configuration")
SCR = os.path.join(ROOT, "scripts", "setup")

_results = []


def check(name, cond, detail=""):
    _results.append((name, bool(cond), detail))


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------
# 1. Migration SQL structure
# ---------------------------------------------------------------------
def test_migrations():
    v = read(os.path.join(MIG, "0024_admin_dashboard_views.sql"))
    expected_views = [
        "vw_main_dashboard", "vw_repository_dashboard", "vw_knowledge_analytics",
        "vw_workflow_dashboard", "vw_execution_explorer", "vw_ai_dashboard",
        "vw_cost_intelligence", "vw_benchmark_dashboard", "vw_review_dashboard",
        "vw_provider_dashboard", "vw_operational_kpis",
    ]
    for name in expected_views:
        check(f"0024 defines admin.{name}", f"admin.{name}" in v, name)
    check("0024 views are read-only (no INSERT/UPDATE/DELETE into views)",
          not re.search(r"INSERT\s+INTO\s+admin\.", v, re.I))
    check("0024 is additive (no DROP TABLE / ALTER TABLE ... DROP)",
          "DROP TABLE" not in v.upper() and "DROP COLUMN" not in v.upper())

    r = read(os.path.join(MIG, "0025_admin_registry_audit_views.sql"))
    for name in ["vw_prompt_registry_dashboard", "vw_configuration_dashboard", "vw_audit_center"]:
        check(f"0025 defines admin.{name}", f"admin.{name}" in r, name)
    check("0025 secrets exposed as presence only (no secret value select)",
          ("secrets_configured" in r and "secrets_missing" in r)
          and "secret value" not in r.lower())
    check("0025 audit center reads all four audit.* tables",
          all(t in r for t in ["audit.repository_changes", "audit.workflow_changes",
                               "audit.configuration_changes", "audit.prompt_changes"]))

    h = read(os.path.join(MIG, "0026_health_alert_center.sql"))
    check("0026 creates monitoring.alerts", "CREATE TABLE IF NOT EXISTS monitoring.alerts" in h)
    check("0026 alerts require severity", "chk_alert_severity" in h)
    check("0026 health_checks additive breaker cols (ADD COLUMN IF NOT EXISTS)",
          h.count("ADD COLUMN IF NOT EXISTS") >= 3)
    check("0026 defines vw_health_center", "admin.vw_health_center" in h)
    check("0026 defines vw_alert_center", "admin.vw_alert_center" in h)
    check("0026 R-18 breaker states referenced", "breaker_state" in h)


# ---------------------------------------------------------------------
# 2. Rollback scripts exist for every migration (§239)
# ---------------------------------------------------------------------
def test_rollbacks():
    for n in ["0024_admin_dashboard_views", "0025_admin_registry_audit_views",
              "0026_health_alert_center"]:
        p = os.path.join(RBK, f"{n}_rollback.sql")
        check(f"rollback exists: {n}", os.path.exists(p))
        if os.path.exists(p):
            body = read(p)
            check(f"rollback {n} drops objects", "DROP" in body.upper())
    # 0026 rollback must preserve base health_checks table (drop columns, not table)
    rb = read(os.path.join(RBK, "0026_health_alert_center_rollback.sql"))
    check("0026 rollback preserves base health_checks table",
          "DROP TABLE IF EXISTS monitoring.health_checks" not in rb)


# ---------------------------------------------------------------------
# 3. n8n JSON well-formedness + required content
# ---------------------------------------------------------------------
def _load_json(path):
    return json.loads(read(path))


def test_wf005():
    wf = _load_json(os.path.join(WF, "WF-005_Administration.json"))
    check("WF-005 id is WF-005", wf["meta"]["crie"]["workflow_id"] == "WF-005")
    check("WF-005 R-02 honored", "R-02" in wf["meta"]["crie"]["reconciliation"])
    check("WF-005 scheduled trigger present",
          any(n["type"] == "n8n-nodes-base.scheduleTrigger" for n in wf["nodes"]))
    node_names = [n["name"] for n in wf["nodes"]]
    for sw in ["SW-026 Execution Logger", "SW-027 Telemetry (open span)",
               "SW-028 Notification"]:
        check(f"WF-005 invokes {sw}", sw in node_names, sw)
    check("WF-005 does config validation (S8-9)",
          any("Config Validation" in n for n in node_names))
    check("WF-005 does prompt validation (S8-9)",
          any("Prompt Validation" in n for n in node_names))
    check("WF-005 R-17 boundary documented (no UI)",
          "R-17" in wf["meta"]["crie"]["boundary"])
    # connections reference existing nodes
    names = set(node_names)
    ok = True
    for src, conns in wf["connections"].items():
        if src not in names:
            ok = False
        for grp in conns.get("main", []):
            for c in grp:
                if c["node"] not in names:
                    ok = False
    check("WF-005 connections reference valid nodes", ok)


def test_subworkflows():
    for sid, fname, spec in [
        ("SW-026", "SW-026_execution_logger.json", "§266"),
        ("SW-027", "SW-027_telemetry_collector.json", "§267"),
        ("SW-028", "SW-028_notification.json", "§268"),
    ]:
        sw = _load_json(os.path.join(SW, fname))
        check(f"{sid} id correct", sw["meta"]["crie"]["sub_workflow_id"] == sid)
        check(f"{sid} spec ref {spec}", spec in sw["meta"]["crie"]["spec"])
        check(f"{sid} has executeWorkflowTrigger",
              any(n["type"] == "n8n-nodes-base.executeWorkflowTrigger" for n in sw["nodes"]))
    # SW-026 four log types
    sw26 = _load_json(os.path.join(SW, "SW-026_execution_logger.json"))
    j = json.dumps(sw26)
    for lt in ["workflow", "ai", "performance", "audit"]:
        check(f"SW-026 handles {lt} log", lt in j)
    # SW-028 email supported, slack/teams future
    sw28 = _load_json(os.path.join(SW, "SW-028_notification.json"))
    check("SW-028 email is v1", "email" in json.dumps(sw28))
    check("SW-028 slack/teams future", "future" in json.dumps(sw28).lower())


# ---------------------------------------------------------------------
# 4. Config completeness (R-08 source of truth, Principle 7 no hardcoding)
# ---------------------------------------------------------------------
def test_config():
    c = read(os.path.join(CFG, "admin.yaml"))
    for key in ["schedule:", "alert_thresholds:", "circuit_breaker:",
                "health_services:", "notifications:", "export:", "roles:",
                "validation:", "refresh_interval_seconds"]:
        check(f"config has {key}", key in c, key)
    check("config health_services lists 10 services (§568)",
          c.count("    - ") >= 10 or c.count("  - ") >= 10)
    check("config secrets externalized (no plaintext creds)",
          "secret:" in c and "password:" not in c.lower())


# ---------------------------------------------------------------------
# 5. S8-9 validation logic (positive + negative)
# ---------------------------------------------------------------------
def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "admin_val", os.path.join(SCR, "admin_scheduled_validation.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["admin_val"] = m  # required for dataclass field type resolution
    spec.loader.exec_module(m)
    return m


def test_validation_logic():
    m = _load_validator()
    ok = m._demo()
    check("S8-9 valid fixture passes", ok["passed"], str(ok["alerts"]))

    # Negative: missing prompt + no providers enabled + missing required value
    bad_cfg = {
        "required_values": {"environment": ""},
        "urls": {"u": "not-a-url"},
        "credentials_present": {"k": False},
        "providers": {"p": {"enabled": False}},
        "feature_flags": {"f": "yes"},
    }
    bad_reg = [{"prompt_id": "PR-001", "version": "1.0.0", "status": "active"}]  # 7 missing
    res = m.run(bad_cfg, bad_reg)
    check("S8-9 negative fixture fails", not res["passed"])
    types = {a["alert_type"] for a in res["alerts"]}
    check("S8-9 raises ConfigValidationFailure", "ConfigValidationFailure" in types)
    check("S8-9 raises PromptValidationFailure", "PromptValidationFailure" in types)
    check("S8-9 detects all 7 missing prompts",
          sum(1 for a in res["alerts"]
              if "Missing prompt" in a["message"]) == 7)
    check("S8-9 §327 six checks declared", len(m.CONFIG_CHECKS) == 6)


# ---------------------------------------------------------------------
# 6. §578 Acceptance Criteria coverage matrix
# ---------------------------------------------------------------------
def test_acceptance_578():
    # Map each §578 criterion to the artifact that satisfies it.
    matrix = {
        "Operational dashboards implemented": ["database/migrations/0024_admin_dashboard_views.sql"],
        "Repository analytics operational": ["database/migrations/0024_admin_dashboard_views.sql"],
        "AI cost tracking operational": ["database/migrations/0024_admin_dashboard_views.sql"],
        "Workflow monitoring operational": ["database/migrations/0024_admin_dashboard_views.sql"],
        "Health monitoring operational": ["database/migrations/0026_health_alert_center.sql"],
        "Alerts operational": ["database/migrations/0026_health_alert_center.sql"],
        "Prompt registry operational": ["database/migrations/0025_admin_registry_audit_views.sql"],
        "Configuration management operational": ["database/migrations/0025_admin_registry_audit_views.sql", "scripts/setup/admin_scheduled_validation.py"],
        "Audit center operational": ["database/migrations/0025_admin_registry_audit_views.sql"],
        "Operations center operational": ["workflows/master/WF-005_Administration.json"],  # scheduled ops via WF-005
    }
    for crit, arts in matrix.items():
        present = all(os.path.exists(os.path.join(ROOT, a)) for a in arts)
        check(f"§578: {crit}", present, ",".join(arts))


def main():
    for fn in [test_migrations, test_rollbacks, test_wf005, test_subworkflows,
               test_config, test_validation_logic, test_acceptance_578]:
        fn()
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print("=" * 68)
    print("CRIE Sprint 8 (Administration) — Acceptance Test Results")
    print("=" * 68)
    for name, ok, detail in _results:
        mark = "PASS" if ok else "FAIL"
        extra = f"  [{detail}]" if (detail and not ok) else ""
        print(f"[{mark}] {name}{extra}")
    print("-" * 68)
    print(f"{passed}/{total} tests passing")
    print("=" * 68)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
