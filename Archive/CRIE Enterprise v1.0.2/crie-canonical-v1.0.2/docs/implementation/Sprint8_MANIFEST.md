# CRIE Sprint 8 (Administration) — Bundle Manifest · v0.9.0

All Rights Reserved, Copyright © 2026 Dawod Manasra.

| Path | Backlog | Spec | Purpose |
|---|---|---|---|
| workflows/WF-005_administration.json | S8-2/3/9 | §157,§159,R-02,R-17,R-18 | Scheduled Administration master workflow |
| sub-workflows/SW-026_execution_logger.json | S8-8 | §266 | Workflow/AI/Performance/Audit logs |
| sub-workflows/SW-027_telemetry_collector.json | S8-8 | §267 | Runtime/tokens/cost/provider telemetry |
| sub-workflows/SW-028_notification.json | S8-8 | §268 | Email (v1); Slack/Teams future |
| migrations/0024_admin_dashboard_views.sql | S8-1/4/5 | §558–567,§577,§198,§533,§560,R-17 | 11 operational dashboard views |
| migrations/0025_admin_registry_audit_views.sql | S8-6/7 | §570–572,§230,R-17 | Prompt/Config/Audit views |
| migrations/0026_health_alert_center.sql | S8-3 | §568,§569,§387,R-18 | Alerts table + breaker cols + views |
| migrations/rollback/*.sql | — | §239 | Matching rollbacks (base tables preserved) |
| scripts/admin_scheduled_validation.py | S8-9 | §327,§157,§174 | Config + prompt validation logic |
| config/admin.config.yaml | S8-9 + all | R-08,§387,§568,§575,§576,Principle 7 | Authored config source of truth |
| prompts/README.md | — | R-04,§608,§612 | No new prompt IDs (documented) |
| tests/test_sprint8.py | — | §578,§609 | 83/83 acceptance tests |
| docs/SPRINT8_ADMINISTRATION.md | — | §609 | Module documentation |
| examples/example_input.json, example_output.json | — | §609 | Example I/O |
| PROJECT_STATUS.md, CHANGELOG.md, VERSION, VERSION_TAG.txt, COMMIT_MESSAGE.txt | — | governance | Status, changelog, version, tag, commit |

**Migration order:** 0024 → 0025 → 0026. All additive; each has a rollback.
**Verification:** `python3 tests/test_sprint8.py` → 83/83. `python3 scripts/admin_scheduled_validation.py` → exit 0.
**Tag:** v0.9.0. **Exit gate:** Administration Console operational (views + BI surface).
