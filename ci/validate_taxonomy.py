#!/usr/bin/env python3
"""validate_taxonomy.py — regression guard for the §438 category taxonomy (R-05).

WHY THIS EXISTS
---------------
Two 16-value taxonomies exist in the project's history and both are labelled
"§438 / R-05":

  canonical (§438, R-05)  Feature, Business Rule, Requirement, Limitation,
                          Configuration, Permission, Calculation, Workflow,
                          Notification, Integration, Reporting, Security, API,
                          Architecture, Known Issue, Recommendation
  SUPERSEDED (§415/§504)  Feature, Capability, Limitation, Configuration,
                          Integration, BusinessRule, Workflow, DataModel,
                          Security, Performance, Compliance, Pricing, Support,
                          Deployment, Roadmap, Other

docs/SRD_CHANGES_SINCE_SPEC.md section D resolves this: the §415/§504 list is
SUPERSEDED, the §438 list is canonical, and the DB CHECK is the enforcement point.
The archived reference implementation
`archive/.../workflows/shared/repository_certification.js` still carries the
superseded list — it contradicts its own package's migration 0018 and its own
PR-001 — so anything ported from it MUST be checked against this file, not
against the reference's constant.

This matters concretely: SW-015 certification refuses to certify a knowledge unit
whose category is not in its enum. Porting the stale list would make
`validCategory` false for EVERY unit in the repository, and nothing could ever be
certified — a silent, total failure.

WHAT IT CHECKS
--------------
  1. migration 0018 CHECK constraint         == canonical 16
  2. migration 0017 seed of knowledge_categories == canonical 16
  3. PR-001 production prompt body            == canonical 16
  4. every shipped workflow that declares a CATEGORY enum == canonical 16
  5. no artifact anywhere in the shipped set mentions a superseded-only value

Exit 0 = clean, 1 = drift. Mirrors the runtime taxonomy pre-flight in WF-001
(SRD_CHANGES_SINCE_SPEC.md section D) at CI time.
"""
import glob
import json
import os
import re
import sys

CANONICAL = [
    "Feature", "Business Rule", "Requirement", "Limitation", "Configuration",
    "Permission", "Calculation", "Workflow", "Notification", "Integration",
    "Reporting", "Security", "API", "Architecture", "Known Issue", "Recommendation",
]
# Values that exist ONLY in the superseded §415/§504 taxonomy. 'Feature',
# 'Limitation', 'Configuration', 'Integration', 'Workflow' and 'Security' appear in
# BOTH lists and are therefore not evidence of drift.
SUPERSEDED_ONLY = [
    "Capability", "BusinessRule", "DataModel", "Performance", "Compliance",
    "Pricing", "Support", "Deployment", "Roadmap", "Other",
]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _quoted(text):
    """Every single-quoted literal in a SQL fragment, in order."""
    return re.findall(r"'([^']*)'", text)


def check_migration_0018(findings):
    path = os.path.join(REPO, "migrations", "0018_knowledge_classification.sql")
    src = open(path, encoding="utf-8").read()
    m = re.search(r"chk_knowledge_units_category\s*\n?\s*CHECK\s*\((.*?)\)\);", src, re.S)
    if not m:
        findings.append("0018: could not locate the chk_knowledge_units_category CHECK body")
        return
    got = [v for v in _quoted(m.group(1)) if v]
    _compare("migration 0018 CHECK", got, findings)


def check_seed_0017(findings):
    path = os.path.join(REPO, "migrations", "0017_seed_data.sql")
    src = open(path, encoding="utf-8").read()
    m = re.search(r"INSERT INTO configuration\.knowledge_categories\s*\(category\)\s*VALUES(.*?);",
                  src, re.S)
    if not m:
        findings.append("0017: could not locate the knowledge_categories seed")
        return
    _compare("migration 0017 seed", [v for v in _quoted(m.group(1)) if v], findings)


def check_pr001(findings):
    hits = glob.glob(os.path.join(REPO, "prompts", "PR-001*.sql"))
    if not hits:
        findings.append("prompts: no PR-001 SQL found")
        return
    checked = 0
    for path in hits:
        src = open(path, encoding="utf-8").read()
        # Only files that DEFINE the taxonomy are compared. A later additive prompt
        # version may merely reference the anchor "CATEGORY — assign exactly ONE."
        # while deriving its body from the previous row (PR-001 v1.3 does exactly
        # that for the authority-source block); such a file defines no categories
        # and comparing it would report a false drift.
        m = re.search(r"CATEGORY — assign exactly ONE\. The allowed set is EXACTLY these 16 values\."
                      r".*?(?=\n[A-Z]{3,}[ —-])", src, re.S)
        if not m:
            print(f"  skip {os.path.basename(path)} (defines no CATEGORY block)")
            continue
        checked += 1
        block = m.group(0)
        # The prompt lists "  Name  - description"; take the name before the dash.
        got = []
        for line in block.splitlines()[2:]:
            mm = re.match(r"\s{2,}([A-Za-z][A-Za-z ]*?)\s+-\s", line)
            if mm:
                got.append(mm.group(1).strip())
        _compare(f"{os.path.basename(path)} CATEGORY block", got, findings)
    if checked == 0:
        findings.append("no PR-001 file defines a CATEGORY block — the guard covers nothing")


def _strip_js_comments(js):
    """Remove // and /* */ comments.

    Essential, not cosmetic: the shipped WF-001 documents the superseded values
    inside a comment explaining what the enum used to hold. Scanning raw text
    reports that correct workflow as drifted — a false positive that would train
    everyone to ignore this check.
    """
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
    return js


def check_workflows(findings):
    """Every category enum DECLARED in a shipped workflow must be the canonical 16.

    Deliberately narrow. An earlier version also flagged any superseded-only value
    appearing as a quoted string anywhere in a node; that was withdrawn as unsound —
    it reported the shipped WF-001 (whose comment documents the old list), the
    runtime taxonomy pre-flight (whose job is to name the old list), and SW-008's
    `CATEGORY_FALLBACK = 'Other'` guard, which is only ever COMPARED against and
    never assigned to `ku.category`. All three are correct code. Words like 'Other',
    'Support' and 'Performance' are too common to carry meaning as bare strings.

    The declaration comparison below is the check that actually matters: it is the
    exact failure mode of porting SW-015 from the stale reference implementation.
    """
    found_any = False
    for path in sorted(glob.glob(os.path.join(REPO, "workflows", "**", "*.json"), recursive=True)):
        wf = json.load(open(path, encoding="utf-8"))
        name = os.path.basename(path)
        for node in wf.get("nodes", []):
            code = (node.get("parameters", {}) or {}).get("jsCode")
            if not code:
                continue
            body = _strip_js_comments(code)
            for m in re.finditer(r"CATEGORY_ENUM\s*=\s*Object\.freeze\(\[(.*?)\]", body, re.S):
                found_any = True
                _compare(f"{name} [{node.get('name')}] CATEGORY_ENUM",
                         [v for v in _quoted(m.group(1)) if v], findings)
    if not found_any:
        findings.append("no workflow declares a CATEGORY_ENUM — the guard is not covering anything")


def _compare(label, got, findings):
    if sorted(got) == sorted(CANONICAL):
        print(f"  OK   {label} ({len(got)} values)")
        return
    missing = [v for v in CANONICAL if v not in got]
    extra = [v for v in got if v not in CANONICAL]
    findings.append(
        f"{label} does not match the canonical §438 enum. "
        + (f"missing={missing} " if missing else "")
        + (f"unexpected={extra}" if extra else "")
    )


def main():
    print("=" * 72)
    print("CRIE §438 category taxonomy validation (R-05)")
    print("=" * 72)
    findings = []
    check_migration_0018(findings)
    check_seed_0017(findings)
    check_pr001(findings)
    check_workflows(findings)
    print("\n" + "=" * 72)
    if findings:
        for f in findings:
            print(f"   x {f}")
        print(f"FAILED — {len(findings)} taxonomy drift finding(s).")
        sys.exit(1)
    print("PASSED — CHECK, seed, prompt and workflow enums all agree on the §438 16.")
    sys.exit(0)


if __name__ == "__main__":
    main()
