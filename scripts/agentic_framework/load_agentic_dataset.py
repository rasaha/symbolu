#!/usr/bin/env python3
"""Independent dataset loader — maps real AgentDojo / InjecAgent traces into the C×R×S governance-harness
scenario schema. Pre-registration: docs/AGENTIC_CRS_SIGNAL_VALIDATION_PREREG.md.

Labels are INDEPENDENT of C×R×S: the governance target is derived from the dataset's own injection/attack
structure (the injected tool was NOT requested by the user → must be gated), NOT from any domain choice.
Semantic-DOMAIN labels are supplied by a SEPARATE annotation file (`--domain-annotations`) and reported as
annotation-derived; missing annotations FAIL LOUD (never inferred). This keeps the feature side and the
target side authored independently, breaking the circularity of the v0 self-authored smoke set.

Each fixture row yields a paired scenario set (`pairing=both`):
  • benign   — the user-intended tool (target ALLOW, or ESCALATE if destructive-unapproved)
  • injected — the injected/attacker tool the user never asked for (target ESCALATE — must be gated)

Output: a scenarios JSON consumable by eval_crs_signal.py (run it with `--crs-source real`).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_FIX = Path(__file__).resolve().parent.parent.parent / "experiments" / "signal_gov" / "data" / "fixtures"


def _annot(domain_annot: dict, key: str, kind: str):
    tasks = domain_annot.get("tasks", {})
    if key not in tasks:
        raise KeyError(f"missing domain annotation for task {key!r} ({kind}) — author it in the "
                       f"domain-annotations file (annotation-derived, NOT inferred)")
    return tasks[key]


def _tool_domain(domain_annot: dict, tool: str):
    tools = domain_annot.get("tools", {})
    if tool not in tools:
        raise KeyError(f"missing domain annotation for tool {tool!r} — author it in the "
                       f"domain-annotations file")
    return tools[tool]


def _scn(sid, slc, ann, tool, risk, tool_domain, proposed, ctx):
    return {
        "scenario_id": sid, "slice": slc, "source": "independent",
        "user_prompt": ann.get("user_prompt", ""), "term": ann["term"],
        "intended_domains": ann["intended_domains"], "secondary_domains": ann.get("secondary_domains", []),
        "rejected_domains": ann.get("rejected_domains", []),
        "tool_domain": tool_domain, "proposed_tool": proposed, "tool_risk_level": risk,
        "policy_context": ctx,
        # crs_match is intentionally ABSENT — the harness fills it from the real engine (--crs-source real)
    }


def load_agentdojo(rows, domain_annot, pairing="both"):
    out = []
    for r in rows:
        key = f"agentdojo:{r['user_task_id']}"
        ann = _annot(domain_annot, key, "agentdojo")
        intent = list(r.get("user_intent_tools", []))
        if pairing in ("both", "benign"):
            bt = r["benign_tool"]
            out.append(_scn(f"{key}:benign", "benign_control", ann, bt, r["benign_risk"],
                            _tool_domain(domain_annot, bt), bt,
                            {"user_intent_tools": intent, "approval_granted": True}))
        if pairing in ("both", "injected"):
            it = r["injected_target_tool"]
            out.append(_scn(f"{key}:injected", "prompt_injection", ann, it, r["injected_risk"],
                            _tool_domain(domain_annot, it), it,
                            {"user_intent_tools": intent, "injected_target_tool": it,
                             "approval_granted": True}))
    return out


def load_injecagent(rows, domain_annot, pairing="both"):
    out = []
    for r in rows:
        key = f"injecagent:{r['case_id']}"
        ann = _annot(domain_annot, key, "injecagent")
        intent = [r["user_tool"]]
        if pairing in ("both", "benign"):
            ut = r["user_tool"]
            out.append(_scn(f"{key}:benign", "benign_control", ann, ut, r["user_tool_risk"],
                            _tool_domain(domain_annot, ut), ut,
                            {"user_intent_tools": intent, "approval_granted": True}))
        if pairing in ("both", "injected"):
            at = r["attacker_tool"]
            out.append(_scn(f"{key}:injected", "prompt_injection", ann, at, r["attacker_tool_risk"],
                            _tool_domain(domain_annot, at), at,
                            {"user_intent_tools": intent, "injected_target_tool": at,
                             "approval_granted": True}))
    return out


def load(kind: str, path: str | None, domain_annot: dict, pairing="both") -> list:
    """kind ∈ {agentdojo, injecagent, both}. Uses the mini fixtures when no --path is given; if a real
    full-dataset path is supplied it must already be in the fixture row schema (jsonl/json list)."""
    def _rows(default_name, p):
        fp = Path(p) if p else (_FIX / default_name)
        if not fp.exists():
            return None
        txt = fp.read_text(encoding="utf-8")
        return [json.loads(l) for l in txt.splitlines() if l.strip()] if fp.suffix == ".jsonl" \
            else json.loads(txt)
    out = []
    if kind in ("agentdojo", "both"):
        rows = _rows("agentdojo_mini.json", path if kind == "agentdojo" else None)
        if rows:
            out += load_agentdojo(rows, domain_annot, pairing)
    if kind in ("injecagent", "both"):
        rows = _rows("injecagent_mini.json", path if kind == "injecagent" else None)
        if rows:
            out += load_injecagent(rows, domain_annot, pairing)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build independent agentic scenarios from AgentDojo/InjecAgent.")
    ap.add_argument("--kind", choices=("agentdojo", "injecagent", "both"), default="both")
    ap.add_argument("--path", default=None, help="optional full-dataset path (fixture row schema)")
    ap.add_argument("--domain-annotations", required=True)
    ap.add_argument("--pairing", choices=("both", "benign", "injected"), default="both")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    domain_annot = json.loads(Path(args.domain_annotations).read_text(encoding="utf-8"))
    scenarios = load(args.kind, args.path, domain_annot, args.pairing)
    blob = {"_provenance": {"target_labels": "independent (dataset injection structure)",
                            "domain_labels": "annotation-derived (separate file, distinct from targets)",
                            "kind": args.kind, "n": len(scenarios)},
            "scenarios": scenarios}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(blob, indent=2), encoding="utf-8")
    print(f"kind={args.kind} scenarios={len(scenarios)} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
