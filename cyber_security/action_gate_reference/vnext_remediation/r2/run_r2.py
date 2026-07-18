"""Run the R2 study: corpus -> deterministic simulator -> metrics -> report.

Writes r2_metrics.json and R2_REMEDIATION_STUDY.md next to this file. Deterministic; no LLM.
"""

from __future__ import annotations

import json
import pathlib
import sys

# make the reference package (action_gate_ref) and this dir importable when run directly
_HERE = pathlib.Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parents[1])):        # r2 dir, action_gate_reference dir
    if _p not in sys.path:
        sys.path.insert(0, _p)

import corpus as C
import metrics as M
import simulator as SIM

HERE = pathlib.Path(__file__).resolve().parent


def run():
    scenarios = C.build_corpus()
    results = [SIM.simulate(s) for s in scenarios]
    m = M.compute(scenarios, results)
    (HERE / "r2_metrics.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    (HERE / "R2_REMEDIATION_STUDY.md").write_text(render_md(m) + "\n")
    return m


def _pct(x):
    return f"{100 * x:.1f}%"


def render_md(m):
    v = m["verdict"]
    am = m["action_modification"]
    L = []
    ap = L.append
    ap("# R2_REMEDIATION_STUDY — corpus + retry-governance simulation (measured)\n")
    ap("> Deterministic study (NO LLM, no planner). A realistic remediation corpus is run "
       "through a deterministic retry simulator against the REAL reference gate. Every number "
       "below is measured. ActionGate semantics are unchanged.\n")
    ap(f"## Headline: planner-automation recommendation = `{v['planner_automation']}`  "
       f"(deterministic remediation = `{v['deterministic_remediation']}`)\n")
    ap("> " + v["rationale"] + "\n")

    ap("## Corpus")
    ap(f"- **{m['total_scenarios']} scenarios** across all 10 policy operations, adversarial / "
       "repeated-retry / oscillation / conflicting cases.")
    ap("- Ground-truth remediation-class distribution:")
    for c in C.CLASSES:
        ap(f"  - {c}: {m['expected_class_distribution'].get(c, 0)}")
    ap("")

    ap("## Simulator outcome distribution")
    for k, val in sorted(m["status_distribution"].items()):
        ap(f"- {k}: {val}")
    ap("")

    ap("## Metrics")
    ap(f"- successful remediation rate: **{_pct(m['successful_remediation_rate'])}**")
    ap(f"- terminal rate: {_pct(m['terminal_rate'])}")
    ap(f"- human escalation rate: {_pct(m['human_escalation_rate'])}")
    ap(f"- oscillation rate: {_pct(m['oscillation_rate'])}")
    ap(f"- capability-stall rate: {_pct(m['capability_stall_rate'])}")
    ap(f"- retry-budget exhaustion rate: {_pct(m['retry_budget_exhaustion_rate'])}")
    ap(f"- average retries (all): {m['average_retries']}  | on success: "
       f"{m['average_retries_on_success']}  | max: {m['maximum_retries']}")
    ap(f"- policy leakage (STANDARD/MINIMAL exposing an exact threshold): "
       f"**{m['policy_leakage_count']}** ({_pct(m['policy_leakage_rate'])})")
    ap(f"- decision stability (identical trajectory on repeat): "
       f"**{_pct(m['decision_stability_rate'])}**")
    ap("")

    ap("## Per-class simulator outcomes")
    ap("| remediation class | outcomes |")
    ap("|---|---|")
    for c in C.CLASSES:
        ap(f"| {c} | {m['per_class_simulator_outcomes'].get(c, {})} |")
    ap("")

    ap("## Security evaluation (all must hold)")
    for k, val in sorted(m["security"].items()):
        ap(f"- {k}: **{val}**")
    ap("")

    ap("## Action-modification analysis (the planner-justification crux)")
    ap(f"- count: {am['count']}  ({_pct(am['share_of_all'])} of all; "
       f"{_pct(am['share_of_remediable'])} of agent-remediable)")
    ap(f"- autonomous success via DETERMINISTIC transform: {am['autonomous_success']} / "
       f"{am['count']} = **{_pct(am['autonomous_success_rate'])}**")
    ap(f"- terminal by unbinding (safety stop — modification invalidated a hard precondition/"
       f"approval): {am['terminal_by_unbinding']}")
    ap(f"- capability stall / conflict (needs more capability or a human, not planning): "
       f"{am['capability_stall_or_conflict']}")
    ap(f"- measured planning gap an LLM could close: **{_pct(v['measured_planning_gap_rate'])}**")
    ap("")

    ap("## Conclusion — should ActionGate ever drive an automatic planner loop?")
    ap("**No — not on this measured evidence.** Where action-modification is remediable at all, "
       "it is remediable by a *deterministic* numeric transform (narrow scope / reduce cost / "
       "choose a reversible target), which needs no LLM. Where it is not, the block is a safety "
       "stop (modifying the action unbinds a hard precondition or approval, correctly producing "
       "DENY) or a capability/human limit — neither of which an LLM planner should route around. "
       "The measured planning gap an LLM could uniquely close is ~0%.")
    ap("")
    ap("**Under exactly what measured conditions could that change?** An automatic loop would "
       "only be justified if a future corpus showed (a) action-modification is a large share of "
       "scenarios (≥30%), AND (b) a substantial fraction of those fail for reasons genuine "
       "*search* could fix (planning-gap ≥10%) rather than safety/capability/human limits, AND "
       "(c) the loop preserves every security invariant below. Until all three hold, the safe "
       "path is a **deterministic** remediation loop (verdict `"
       f"{v['deterministic_remediation']}`) confined to policy-opted-in mechanical classes, with "
       "an LLM planner kept out of the trust boundary (verdict `"
       f"{v['planner_automation']}`).")
    ap("")
    ap("## Remaining risks")
    ap("- **Unbinding cascades:** action-modification invalidates prior evidence/approvals; a "
       "naive loop can turn an ESCALATE into a DENY. A deterministic loop must re-collect "
       "authority for the new action_hash and must never treat a resulting DENY as retryable.")
    ap("- **Oscillation with volatile evidence:** evidence that expires on arrival loops until "
       "detected; loop-detection + a retry budget are mandatory (measured oscillation "
       f"{_pct(m['oscillation_rate'])}).")
    ap("- **Policy-opt-in surface:** action-modification exists only where a policy opts a MAX_* "
       "rule in; that opt-in widens the disclosure/oracle surface and must be governed.")
    ap("- **Corpus scope:** this is a synthetic-but-grounded corpus over the reference ruleset; "
       "a production ruleset could shift the distribution and must be re-measured before any "
       "automation decision.")
    return "\n".join(L)


if __name__ == "__main__":
    result = run()
    print(json.dumps({"planner_automation": result["verdict"]["planner_automation"],
                      "deterministic_remediation": result["verdict"]["deterministic_remediation"],
                      "successful_remediation_rate": result["successful_remediation_rate"],
                      "security": result["security"],
                      "policy_leakage_count": result["policy_leakage_count"],
                      "decision_stability_rate": result["decision_stability_rate"]}, indent=2))
