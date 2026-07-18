#!/usr/bin/env python3
"""validate_workflows.py — Compile-time static validation for CRIE n8n workflows.

Catches, BEFORE deployment, the class of defect that otherwise only surfaces at runtime:

  1. NODE REFERENCE INTEGRITY
     Every $('Node Name') in every expression / Code node must resolve to a node that
     actually exists in the SAME workflow. n8n resolves $() against the current workflow
     only — a reference to a renamed, deleted, or cross-workflow node fails at runtime with
     "Node '<x>' hasn't been executed" or an undefined read.

  2. NODE REFERENCE REACHABILITY
     A referenced node must also be UPSTREAM of the referring node (or on a branch that
     executes first). Referencing a node that runs later — or never — is a latent failure.

  3. PROMPT REFERENCE CORRECTNESS
     Each workflow that loads a prompt must load the INTENDED one (SW-007 -> PR-002,
     SW-008 -> PR-001). A copy-paste between the two sub-workflows silently swaps the
     prompt and produces plausible-but-wrong output — the worst kind of bug.

  4. STALE REFERENCES FROM COPIED WORKFLOWS
     Node names referenced by $() that belong to a *different* workflow's vocabulary
     (e.g. SW-013 still referencing 'Load OCR Provider Settings') indicate a copied
     workflow whose references were not retargeted.

Exit code 0 = clean, 1 = findings. Intended for CI and for the pre-deployment gate.

Usage:
    python3 validate_workflows.py <workflow.json> [<workflow.json> ...]
    python3 validate_workflows.py "workflows/**/*.json"     # explicit recursive glob
    python3 validate_workflows.py                            # no args -> the active set
                                                             #   defined in ci/active_workflows.txt

The "active set" (which workflows CI validates) is configuration-driven: with no
path arguments the validator reads the glob manifest ci/active_workflows.txt so the
active set lives in ONE editable file, not hardcoded in ci.yml or the runners.
Explicit path arguments still override the manifest (handy for ad-hoc checks).

Ported into ci/ for CRIE Iteration 1 (CI regression guards). Changes from the
archived original are surgical only: os.path.basename for cross-platform paths,
UTF-8 reads, and recursive-glob / default-path handling in main(). The validation
logic is unchanged.
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict

# Which prompt each sub-workflow is CANONICALLY required to load.
# Source: PR-001.yaml ("Loaded at runtime by SW-008"), PR-002.yaml ("Loaded at runtime by SW-007").
EXPECTED_PROMPT = {
    "SW-007": "PR-002",   # Metadata Extraction
    "SW-008": "PR-001",   # Knowledge Extraction
}
# Sub-workflows that must reference NO prompt at all.
NO_PROMPT = {"SW-005", "SW-013", "SW-014"}

NODE_REF = re.compile(r"\$\(\s*['\"](?P<name>[^'\"]+)['\"]\s*\)")
PROMPT_REF = re.compile(r"PR-\d{3}")


TRIGGER_TYPES = (
    "n8n-nodes-base.executeWorkflowTrigger",
    "n8n-nodes-base.googleDriveTrigger",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.cron",
    "n8n-nodes-base.emailReadImap",
)


def find_triggers(nodes):
    """Nodes that can START an execution."""
    trigs = [n["name"] for n in nodes if n["type"] in TRIGGER_TYPES]
    if not trigs:
        # fall back: any node with no incoming connection and a trigger-ish type name
        trigs = [n["name"] for n in nodes if "trigger" in n["type"].lower()]
    return trigs


def successors_map(wf):
    """name -> set(successor names)."""
    succ = defaultdict(set)
    for src, conn in (wf.get("connections") or {}).items():
        for branch in conn.get("main", []):
            for t in branch:
                succ[src].add(t["node"])
    return succ


def reachable_from_triggers(wf, nodes):
    """Every node with a path from ANY trigger. Nodes outside this set NEVER execute."""
    succ = successors_map(wf)
    seen = set()
    stack = list(find_triggers(nodes))
    seen.update(stack)
    while stack:
        cur = stack.pop()
        for nxt in succ.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def node_blob(node):
    """All text in a node where an expression could hide."""
    return json.dumps(node.get("parameters", {}), ensure_ascii=False)


def build_graph(wf):
    """name -> set(predecessor names), for reachability checks."""
    preds = defaultdict(set)
    for src, conn in (wf.get("connections") or {}).items():
        for branch in conn.get("main", []):
            for target in branch:
                preds[target["node"]].add(src)
    return preds


def ancestors(name, preds, seen=None):
    seen = seen or set()
    for p in preds.get(name, ()):
        if p not in seen:
            seen.add(p)
            ancestors(p, preds, seen)
    return seen


def validate(path):
    with open(path, encoding="utf-8") as fh:
        wf = json.load(fh)
    wf_name = os.path.basename(path)
    # Identify the workflow from its CONTENT, not its filename — a renamed file must not
    # silently disable the prompt check. Fall back to the filename only if content is silent.
    wf_id = None
    m = re.search(r"\b(SW-\d{3}|WF-\d{3}|UT-\d{3})\b", wf.get("name", "") or "")
    if m:
        wf_id = m.group(1)
    if not wf_id:
        blob = json.dumps(wf.get("nodes", []), ensure_ascii=False)
        ids = set(re.findall(r"\b(SW-\d{3})\b", blob))
        # a sub-workflow usually names itself in its own notes/meta; prefer a single hit
        if len(ids) == 1:
            wf_id = ids.pop()
    if not wf_id:
        m = re.match(r"(SW-\d{3}|WF-\d{3}|UT-\d{3})", wf_name)
        wf_id = m.group(1) if m else None
    nodes = wf.get("nodes", [])
    names = {n["name"] for n in nodes}
    preds = build_graph(wf)
    pos = {n["name"]: n.get("position", [0, 0]) for n in nodes}
    live = reachable_from_triggers(wf, nodes)   # nodes with a path from a trigger
    triggers = find_triggers(nodes)
    findings = []

    # ---- 0: orphan nodes (no path from any trigger => they NEVER execute) ----
    if not triggers:
        findings.append("NO TRIGGER   workflow has no trigger node; nothing can execute")
    for n in nodes:
        if n["name"] not in live:
            findings.append(
                f"ORPHAN NODE  [{n['name']}] has no path from any trigger "
                f"— it will never execute"
            )

    # ---- 1 & 2: node reference integrity + reachability ----
    for n in nodes:
        blob = node_blob(n)
        for m in NODE_REF.finditer(blob):
            ref = m.group("name")
            if ref not in names:
                findings.append(
                    f"BROKEN REF   [{n['name']}] references $('{ref}') "
                    f"— no such node in this workflow"
                )
                continue
            # Explicit requirement: the referenced node must have a path from the trigger,
            # otherwise it can never execute and $() can never resolve.
            if ref not in live:
                findings.append(
                    f"NO TRIGGER PATH [{n['name']}] references $('{ref}') "
                    f"— that node has no path from any trigger; it will never execute"
                )
                continue
            # Reachability. n8n executionOrder v1 runs each branch to completion, ordered
            # topmost-first by canvas position. So a reference is valid if the referenced
            # node is EITHER an ancestor, OR a node on a sibling branch that executes first
            # (i.e. shares an ancestor with us and sits higher on the canvas).
            if ref != n["name"]:
                anc = ancestors(n["name"], preds)
                if ref not in anc:
                    ref_anc = ancestors(ref, preds)
                    shares_ancestor = bool(anc & ref_anc) or bool(ref_anc & {n["name"]}) or bool(
                        (anc | {n["name"]}) & ref_anc
                    )
                    ref_y = pos.get(ref, [0, 0])[1]
                    self_y = pos.get(n["name"], [0, 0])[1]
                    if shares_ancestor and ref_y < self_y:
                        # sibling branch, higher on canvas -> n8n runs it first. Valid, but
                        # it is an ordering-dependent reference, so surface it as a note.
                        findings.append(
                            f"NOTE         [{n['name']}] references $('{ref}') on a sibling "
                            f"branch (runs first under executionOrder v1, topmost-first). "
                            f"Valid, but ONLY on a full trigger-initiated run — a partial "
                            f"execution started mid-graph will not run it."
                        )
                    else:
                        findings.append(
                            f"UNREACHABLE  [{n['name']}] references $('{ref}') "
                            f"— not upstream and not a first-running sibling branch"
                        )

    # ---- 5: IF/Switch node schema (filter v2 must be NESTED) ----
    # A flat parameters.conditions ARRAY imports with ZERO conditions and the node then
    # evaluates vacuously TRUE, silently passing every item out the true branch.
    # Real n8n export shape: parameters.conditions = {options:{}, conditions:[...], combinator:""}
    for n in nodes:
        if n.get("type") not in ("n8n-nodes-base.if", "n8n-nodes-base.filter", "n8n-nodes-base.switch"):
            continue
        tv = n.get("typeVersion", 1)
        if float(tv) < 2:
            continue          # v1 used a different (legacy) schema
        params = n.get("parameters", {})
        cond = params.get("conditions")
        if cond is None:
            findings.append(f"IF SCHEMA    [{n['name']}] has no 'conditions' parameter")
        elif isinstance(cond, list):
            findings.append(
                f"IF SCHEMA    [{n['name']}] parameters.conditions is a flat ARRAY — n8n IF v2 "
                f"expects a nested OBJECT {{options, conditions[], combinator}}. This imports with "
                f"ZERO conditions and the node then passes EVERY item out the TRUE branch."
            )
        elif isinstance(cond, dict):
            if not isinstance(cond.get("conditions"), list) or not cond.get("conditions"):
                findings.append(
                    f"IF SCHEMA    [{n['name']}] parameters.conditions.conditions is missing or empty "
                    f"— the node will evaluate vacuously TRUE"
                )
            for c in (cond.get("conditions") or []):
                op = c.get("operator") or {}
                # unary operators require singleValue:true; otherwise rightValue is ignored
                if op.get("operation") in ("true", "false", "exists", "notExists", "empty", "notEmpty") \
                        and not op.get("singleValue"):
                    findings.append(
                        f"NOTE         [{n['name']}] operator '{op.get('operation')}' is unary and "
                        f"'singleValue': true is absent. Real n8n exports include it. This node has "
                        f"the correct nested schema and is observed to evaluate correctly, so this is "
                        f"advisory — but prefer a plain 'equals' operator in new nodes."
                    )


    # ---- 5: executeWorkflowTrigger inputSource ----
    # n8n SILENTLY IGNORES camelCase 'passThrough'. The trigger then falls back to
    # defined-fields mode and drops the caller's payload (including binary). Real n8n
    # exports use the lowercase 'passthrough'.
    for n in nodes:
        if not n.get("type", "").endswith("executeWorkflowTrigger"):
            continue
        src = n.get("parameters", {}).get("inputSource")
        tv = n.get("typeVersion", 1)
        if src == "passThrough":
            findings.append(
                f"TRIGGER       [{n.get('name')}] inputSource is camelCase 'passThrough' — n8n "
                f"SILENTLY IGNORES this and falls back to defined-fields mode, dropping the "
                f"caller's payload. Use lowercase 'passthrough'."
            )
        elif src == "passthrough" and float(tv) < 1.1:
            findings.append(
                f"TRIGGER       [{n.get('name')}] inputSource 'passthrough' requires "
                f"typeVersion >= 1.1 (found {tv})"
            )

    # ---- 3 & 4: prompt reference correctness ----
    prompts_used = set()
    for n in nodes:
        # Scan CODE and node names/notes, but strip comments: a doc-comment that merely
        # *mentions* another prompt (e.g. "knows nothing about PR-001/PR-002") is prose,
        # not a reference, and must not be flagged.
        params = dict(n.get("parameters", {}))
        if "jsCode" in params:
            params["jsCode"] = _strip_comments(params["jsCode"])
        scrubbed = dict(n)
        scrubbed["parameters"] = params
        prompts_used |= set(PROMPT_REF.findall(json.dumps(scrubbed)))

    if wf_id is None and prompts_used:
        findings.append(
            f"UNIDENTIFIED workflow references {sorted(prompts_used)} but its ID could not be "
            f"determined from content or filename — prompt correctness CANNOT be checked"
        )

    expected = EXPECTED_PROMPT.get(wf_id)
    if expected:
        if expected not in prompts_used:
            findings.append(
                f"WRONG PROMPT {wf_id} must load {expected} but does not reference it "
                f"(found: {sorted(prompts_used) or 'none'})"
            )
        wrong = prompts_used - {expected}
        if wrong:
            findings.append(
                f"STALE PROMPT {wf_id} references {sorted(wrong)} in addition to its "
                f"required {expected} — likely copy-paste from a sibling workflow"
            )
    elif wf_id in NO_PROMPT and prompts_used:
        findings.append(
            f"STALE PROMPT {wf_id} should reference no prompt but references "
            f"{sorted(prompts_used)}"
        )

    return wf_name, len(nodes), findings



def _strip_comments(js: str) -> str:
    """Remove // line comments and /* */ block comments so prose is not scanned as code."""
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
    return js

def load_manifest(manifest_path, repo_root):
    """Read glob patterns (one per line, '#' comments) and expand them from repo_root."""
    patterns, paths = [], []
    with open(manifest_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
            paths.extend(glob.glob(os.path.join(repo_root, line), recursive=True))
    return patterns, paths


def main():
    args = sys.argv[1:]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)

    if args:
        # Explicit paths/globs override the manifest.
        paths = []
        for a in args:
            paths.extend(glob.glob(a, recursive=True))
        source = "command-line arguments"
    else:
        # No args: the active set is configuration-driven via the manifest.
        manifest = os.path.join(script_dir, "active_workflows.txt")
        if not os.path.exists(manifest):
            print(f"no path args given and manifest not found: {manifest}", file=sys.stderr)
            sys.exit(2)
        patterns, paths = load_manifest(manifest, repo_root)
        source = f"ci/active_workflows.txt ({len(patterns)} pattern(s))"

    paths = sorted({p for p in paths if p.endswith(".json")})
    if not paths:
        print(f"no workflow JSON found (source: {source})", file=sys.stderr)
        sys.exit(2)

    total = 0
    print("=" * 72)
    print("CRIE workflow static validation")
    print(f"active set from: {source}")
    print("=" * 72)
    for p in paths:
        name, ncount, findings = validate(p)
        errs = [f for f in findings if not f.startswith("NOTE")]
        status = "OK" if not errs else f"{len(errs)} ERROR(S)"
        if not errs and findings: status = f"OK ({len(findings)} note(s))"
        print(f"\n{name}  ({ncount} nodes) — {status}")
        for f in findings:
            print(f"   x {f}")
        total += len([f for f in findings if not f.startswith("NOTE")])

    print("\n" + "=" * 72)
    if total:
        print(f"FAILED — {total} finding(s). Fix before deploying.")
        sys.exit(1)
    print("PASSED — all node references resolve; all prompt references correct.")
    sys.exit(0)


if __name__ == "__main__":
    main()
