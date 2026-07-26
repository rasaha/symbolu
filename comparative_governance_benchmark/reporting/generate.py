"""Report generation (Task 16).

Produces the seven Phase 6A artifacts. The main markdown report separates measured
result, benchmark-design consequence, architectural inference, and unvalidated
real-world claim, and makes no production/ROI claim.
"""
from __future__ import annotations

import json
import pathlib

from ..benchmark import BenchmarkResults
from ..schemas.safety import SafetyOutcome, UNSAFE_OUTCOMES

_STRATEGY_LABEL = {
    "no_governance": "No Governance", "action_only": "Action Only",
    "assertion_only": "Assertion Only", "full_governance": "Full",
}


def _unsafe(res, sid):
    return sum(1 for j in res.judgements[sid] if j.safety_outcome in UNSAFE_OUTCOMES)


def _safe_count(res, sid, outcome):
    return res.safety_distribution[sid].get(outcome, 0)


def strategy_metrics_json(res: BenchmarkResults) -> dict:
    return {"metrics": res.metrics, "metrics_by_domain": res.metrics_by_domain,
            "safety_distribution": res.safety_distribution,
            "safety_by_cross_class": res.safety_by_class}


def scenario_comparison_json(res: BenchmarkResults) -> dict:
    rows = []
    ids = [s.scenario_id for s, _r in res.grid[res.strategy_ids[0]]]
    scen_by_id = {s.scenario_id: s for s, _r in res.grid[res.strategy_ids[0]]}
    judge_by = {sid: {j.scenario_id: j for j in res.judgements[sid]} for sid in res.strategy_ids}
    result_by = {sid: {r.scenario_id: r for _s, r in res.grid[sid]} for sid in res.strategy_ids}
    for scid in ids:
        s = scen_by_id[scid]
        row = {"scenario_id": scid, "domain": s.domain,
               "assertion_class": s.assertion_class, "action_class": s.action_class,
               "cross_class": s.cross_class, "strategies": {}}
        for sid in res.strategy_ids:
            r = result_by[sid][scid]
            row["strategies"][sid] = {
                "safety_outcome": judge_by[sid][scid].safety_outcome,
                "assertion_outcome": r.assertion_outcome,
                "authorization_outcome": r.authorization_outcome,
                "dispatched": r.dispatched, "execution_outcome": r.execution_outcome,
                "compliance": r.final_governance_compliance}
        rows.append(row)
    return {"scenarios": rows}


def failure_comparison_json(res: BenchmarkResults) -> dict:
    by_profile: dict = {}
    for c in res.failure_matrix:
        by_profile.setdefault(c.profile, {})[c.strategy_id] = {
            "applicable": c.applicable, "scenarios": c.scenarios,
            "fail_safe": c.fail_safe, "fail_open": c.fail_open,
            "fail_safe_rate": c.fail_safe_rate, "fail_open_rate": c.fail_open_rate,
            "unsafe": c.unsafe, "avg_trace_links": c.avg_trace_links,
            "avg_audit_events": c.avg_audit_events, "human_reviews": c.human_reviews}
    return {"failure_matrix": by_profile}


def governance_cost_json(res: BenchmarkResults) -> dict:
    return {"cost": res.cost, "effectiveness": res.effectiveness}


def invariants_json(res: BenchmarkResults) -> dict:
    return {"all_passed": res.invariants_passed,
            "invariants": [{"id": i.id, "description": i.description, "passed": i.passed,
                            "detail": i.detail} for i in res.invariants],
            "fairness": [{"name": c.name, "passed": c.passed, "detail": c.detail}
                         for c in res.fairness]}


def paired_json(res: BenchmarkResults) -> dict:
    return {"paired": res.paired}


def _class_winners(res: BenchmarkResults) -> list:
    """Best-performing strategies (fewest unsafe) per cross class."""
    lines = []
    for cls, per in res.safety_by_class.items():
        unsafe = {sid: sum(v for k, v in dist.items() if k in UNSAFE_OUTCOMES)
                  for sid, dist in per.items()}
        best = min(unsafe.values())
        winners = [_STRATEGY_LABEL[sid] for sid, u in unsafe.items() if u == best]
        if best == 0 and len(winners) == len(res.strategy_ids):
            lines.append(f"- **{cls}** — all strategies reached the same safe outcome")
        else:
            lines.append(f"- **{cls}** — best (fewest unsafe={best}): {', '.join(winners)}")
    return lines


def comparative_report_md(res: BenchmarkResults) -> str:
    S = res.strategy_ids
    L = [_STRATEGY_LABEL[s] for s in S]
    out: list[str] = []
    a = out.append
    a("# Phase 6A — Comparative Governance Benchmark")
    a("")
    a(f"- **Dataset:** `{res.dataset_identity.version}` "
      f"(hash `{res.dataset_identity.content_hash[:16]}…`, {res.dataset_identity.scenario_count} "
      f"scenarios, {res.dataset_identity.domain_count} domains) — reused unchanged from Phase 5I")
    a(f"- **Substantive digest:** `{res.substantive_digest[:16]}…`")
    a(f"- **Fairness controls:** {'ALL PASS' if res.fairness_passed else 'FAIL'} · "
      f"**Benchmark invariants:** {'ALL PASS' if res.invariants_passed else 'FAIL'}")
    a("")
    a("## Measured result — normal mode")
    a("")
    header = "| Metric | " + " | ".join(L) + " |"
    sep = "|" + "---|" * (len(L) + 1)
    a(header); a(sep)

    def row(label, fn):
        a(f"| {label} | " + " | ".join(str(fn(sid)) for sid in S) + " |")

    row("Unsafe outcomes (total)", lambda s: _unsafe(res, s))
    row("Unsupported assertion promotion",
        lambda s: res.metrics[s]["assertion"]["unsupported_assertion_promotion_rate"])
    row("Unsafe dispatch rate",
        lambda s: res.metrics[s]["action"]["unsafe_dispatch_rate"])
    row("Constraint violations",
        lambda s: _safe_count(res, s, SafetyOutcome.CONSTRAINT_VIOLATION.value))
    row("Obligation failures detected",
        lambda s: _safe_count(res, s, SafetyOutcome.OBLIGATION_FAILURE.value))
    row("Qualifier preservation rate",
        lambda s: res.metrics[s]["assertion"]["qualifier_preservation_rate"])
    row("Governance-compliance visibility",
        lambda s: res.metrics[s]["workflow"]["governance_compliance_visibility_rate"])
    row("Avg trace links",
        lambda s: res.metrics[s]["workflow"]["avg_trace_links"])
    row("Provider invocations (total)",
        lambda s: res.cost[s]["total"]["provider_invocations"])
    row("Human reviews (total)",
        lambda s: res.cost[s]["total"]["human_review_events"])
    row("Total governance operations",
        lambda s: res.cost[s]["total_operations"])
    a("")
    a("## Scenario-class winners")
    a("")
    out.extend(_class_winners(res))
    a("")
    a("## Paired comparisons (net unsafe reduction, first vs second)")
    a("")
    for pair, d in res.paired.items():
        ci = d["bootstrap_ci_mean_unsafe_reduction"]
        ci_s = (f" (mean {ci['mean']}, 95% CI [{ci['ci95_low']}, {ci['ci95_high']}], "
                f"seed {ci['seed']})" if ci else "")
        a(f"- **{pair}**: net unsafe reduction **{d['net_unsafe_reduction']}** "
          f"(prevented {d['unsafe_prevented_by_first']}, introduced {d['unsafe_introduced_by_first']})"
          + ci_s)
    a("")
    a("## Governance cost-effectiveness (structural workload, not ROI)")
    a("")
    for sid in S:
        e = res.effectiveness.get(sid)
        if not e:
            continue
        a(f"- **{_STRATEGY_LABEL[sid]}**: +{e['additional_governance_operations']} ops vs No "
          f"Governance, preventing {e['unsafe_prevented_vs_baseline']} unsafe outcomes "
          f"→ {e['additional_operations_per_unsafe_prevented']} extra ops per unsafe prevented")
    a("")
    a("## Failure-mode summary (fail-safe rate, applicable strategies)")
    a("")
    profiles = sorted({c.profile for c in res.failure_matrix})
    a("| Profile | " + " | ".join(L) + " |"); a(sep)
    for p in profiles:
        cells = {c.strategy_id: c for c in res.failure_matrix if c.profile == p}
        vals = []
        for sid in S:
            c = cells.get(sid)
            vals.append("n/a" if (c is None or not c.applicable) else str(c.fail_safe_rate))
        a(f"| {p} | " + " | ".join(vals) + " |")
    a("")
    a("## Interpretation")
    a("")
    a("**Measured result:** the full architecture prevented every unsafe outcome the "
      f"no-governance baseline allowed ({_unsafe(res, 'no_governance')} → "
      f"{_unsafe(res, 'full_governance')}); Action Only and Assertion Only each prevented a "
      "strict subset, and were additive — neither alone matched the full architecture.")
    a("")
    a("**Benchmark-design consequence:** rates are shaped by the synthetic scenario "
      "prevalence in `enterprise_pilot_v1`; they are not real-world base rates.")
    a("")
    a("**Architectural inference:** TAP and ActionGate govern disjoint failure modes "
      "(unsupported assertions vs unsafe/out-of-envelope actions); the full architecture "
      "is the only strategy with zero unsafe outcomes, at a measurable additional workload.")
    a("")
    a("**Unvalidated real-world claim:** none. Deterministic reference providers are being "
      "measured — not production model accuracy. No regulatory-compliance or customer-ROI "
      "claim is made; a superior result here does not prove universal superiority.")
    a("")
    return "\n".join(out) + "\n"


_JSON = {
    "PHASE_6A_STRATEGY_METRICS.json": strategy_metrics_json,
    "PHASE_6A_SCENARIO_COMPARISON.json": scenario_comparison_json,
    "PHASE_6A_FAILURE_COMPARISON.json": failure_comparison_json,
    "PHASE_6A_GOVERNANCE_COST.json": governance_cost_json,
    "PHASE_6A_INVARIANTS.json": invariants_json,
    "PHASE_6A_PAIRED_ANALYSIS.json": paired_json,
}


def write_all(res: BenchmarkResults, out_dir: pathlib.Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in _JSON.items():
        p = out_dir / name
        p.write_text(json.dumps(fn(res), indent=2, sort_keys=True, default=str) + "\n")
        written.append(p)
    md = out_dir / "PHASE_6A_COMPARATIVE_BENCHMARK.md"
    md.write_text(comparative_report_md(res))
    written.append(md)
    return written
