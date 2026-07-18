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
    python3 validate_workflows.py workflows/master/*.json workflows/sub/*.json
"""
import glob
import json
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
    wf = json.load(open(path))
    wf_name = path.split("/")[-1]
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

    # ---- 3 & 4: prompt reference correctness ----
    prompts_used = set()
    for n in nodes:
        prompts_used |= set(PROMPT_REF.findall(node_blob(n)))

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


def main():
    paths = []
    for a in sys.argv[1:]:
        paths.extend(sorted(glob.glob(a)))
    if not paths:
        print("usage: validate_workflows.py <workflow.json> [...]", file=sys.stderr)
        sys.exit(2)

    total = 0
    print("=" * 72)
    print("CRIE workflow static validation")
    print("=" * 72)
    for p in paths:
        name, ncount, findings = validate(p)
        errs = [f for f in findings if not f.startswith("NOTE")]
        status = "OK" if not errs else f"{len(errs)} ERROR(S)"
        if not errs and findings: status = f"OK ({len(findings)} note(s))"
        print(f"\n{name}  ({ncount} nodes) — {status}")
        for f in findings:
            print(f"   ✗ {f}")
        total += len([f for f in findings if not f.startswith("NOTE")])

    print("\n" + "=" * 72)
    if total:
        print(f"FAILED — {total} finding(s). Fix before deploying.")
        sys.exit(1)
    print("PASSED — all node references resolve; all prompt references correct.")
    sys.exit(0)


if __name__ == "__main__":
    main()
