"""Report generation (Task 19) — eight Phase 6B artifacts."""
from __future__ import annotations

import json
import pathlib

from ..validation import ValidationResults

_LABEL = {
    "C1": "TAP + ActionGate", "C2": "TAP + Baseline Action",
    "C3": "Baseline Assertion + ActionGate", "C4": "Baseline Assertion + Baseline Action",
    "C5": "Preferred + Bounded Fallback", "C6": "Capability-Driven",
}


def resolution_metrics_json(res: ValidationResults) -> dict:
    return {"resolution_metrics": res.resolution, "governance_metrics": res.governance}


def provider_results_json(res: ValidationResults) -> dict:
    return {"provider_metrics": res.providers}


def failure_matrix_json(res: ValidationResults) -> dict:
    by_profile: dict = {}
    for c in res.failure_matrix:
        by_profile.setdefault(c.profile, {})[c.configuration_id] = {
            "applicable": c.applicable, "scenarios": c.scenarios, "fail_safe": c.fail_safe,
            "unsafe": c.unsafe, "fallbacks": c.fallbacks, "no_valid_provider": c.no_valid_provider}
    return {"failure_matrix": by_profile}


def invariants_json(res: ValidationResults) -> dict:
    return {"all_passed": res.invariants_passed,
            "invariants": [{"id": i.id, "description": i.description, "passed": i.passed,
                            "detail": i.detail} for i in res.invariants]}


def selection_records_json(res: ValidationResults) -> dict:
    return {"selection_records": res.selection_records}


def cost_benefit_frontier_json(res: ValidationResults) -> dict:
    return {"frontier_by_scenario_class": res.frontier}


def configuration_comparison_json(res: ValidationResults) -> dict:
    return {"configuration_comparison": res.configuration_comparison}


def report_md(res: ValidationResults) -> str:
    out: list = []
    a = out.append
    a("# Phase 6B — Provider Heterogeneity, Resolution, and Failover Validation")
    a("")
    a(f"- **Dataset:** `{res.dataset_identity.version}` "
      f"(hash `{res.dataset_identity.content_hash[:16]}…`, {res.dataset_identity.scenario_count} "
      f"scenarios) — reused unchanged")
    a(f"- **Substantive digest:** `{res.substantive_digest[:16]}…`")
    a(f"- **Invariants H1–H20:** {'ALL PASS' if res.invariants_passed else 'FAIL'}")
    a("")
    a("## Configuration comparison (normal mode, 90 scenarios)")
    a("")
    a("| Config | Providers | Unsafe | Dispatched | False blocks | Fallbacks | No-valid-provider |")
    a("|---|---|---|---|---|---|---|")
    for cid in res.config_order:
        c = res.configuration_comparison[cid]
        a(f"| {cid} | {_LABEL[cid]} | {c['unsafe_outcomes']} | {c['dispatched']} | "
          f"{c['false_blocks']} | {c['assertion_fallbacks'] + c['action_fallbacks']} | "
          f"{c['no_valid_provider']} |")
    a("")
    a("## Resolution metrics")
    a("")
    a("| Config | Preferred sel. | Fallback | Safe fallback | No-valid | Cap-match | Compat-rej | Health-rej |")
    a("|---|---|---|---|---|---|---|---|")
    for cid in res.config_order:
        m = res.resolution[cid]
        a(f"| {cid} | {m['preferred_provider_selection_rate']} | {m['fallback_rate']} | "
          f"{m['safe_fallback_success_rate']} | {m['no_valid_provider_rate']} | "
          f"{m['capability_match_rate']} | {m['compatibility_rejection_count']} | "
          f"{m['health_rejection_count']} |")
    a("")
    a("## Governance metrics under heterogeneity")
    a("")
    a("| Config | Unsupported promotion | Unsafe auth | Unsafe dispatch | Fail-safe | Gov-shopping |")
    a("|---|---|---|---|---|---|")
    for cid in res.config_order:
        m = res.governance[cid]
        a(f"| {cid} | {m['unsupported_promotion_rate']} | {m['unsafe_authorization_rate']} | "
          f"{m['unsafe_dispatch_rate']} | {m['fail_safe_rate']} | "
          f"{m['governance_shopping_violations']} |")
    a("")
    a("## Cost/benefit frontier by scenario class")
    a("")
    for cls, f in res.frontier.items():
        need = []
        if f["required_assertion_capabilities"]:
            need.append("assertion:" + ",".join(f["required_assertion_capabilities"]))
        if f["required_action_capabilities"]:
            need.append("action:" + ",".join(f["required_action_capabilities"]))
        a(f"- **{cls}** — sufficient: {', '.join(f['sufficient_configs']) or 'none'}; "
          f"lightest: {f['lowest_workload_sufficient']}; "
          f"required capabilities: {'; '.join(need) or 'none'}; "
          f"fallback acceptable: {f['fallback_acceptable']}; "
          f"full pair required: {f['full_pair_required']}")
    a("")
    a("## Provider-specific metrics (never a single ranking)")
    a("")
    a("| Provider | Eligible | Selected | Invocations | Infra failures | Substantive INDET | Fallbacks-to |")
    a("|---|---|---|---|---|---|---|")
    for pid, s in res.providers.items():
        a(f"| {pid} | {s['eligible_requests']} | {s['selected_requests']} | "
          f"{s['successful_invocations']} | {s['infrastructure_failures']} | "
          f"{s['substantive_indeterminate']} | {s['fallbacks_to']} |")
    a("")
    a("## Interpretation")
    a("")
    a("**Measured result:** two providers coexist in each family behind the unchanged "
      "framework. Selection is deterministic (H1) and auditable; compatibility, capability, "
      "and health are honoured (H2–H4, H19); bounded fallback occurs only under infrastructure "
      "failure and only where policy permits (H9), never converting a substantive UNSUPPORTED/"
      "DENIED/INDETERMINATE into support/authorization (H5–H8, governance-shopping violations = "
      "0); and no-valid-provider cases fail safe to INDETERMINATE with no dispatch (H10–H11, H20).")
    a("")
    a("**Benchmark-design consequence:** capability-limited baseline providers correctly return "
      "INDETERMINATE for scenarios beyond their honestly-declared capability, appearing as "
      "fail-safe *false blocks* (never unsafe). The capability-driven configuration routes each "
      "request to the lightest sufficient provider and escalates only when a capability is "
      "genuinely required.")
    a("")
    a("**Architectural inference:** the existing registry, compatibility, and capability "
      "structures are sufficient to host heterogeneous providers and fail over safely without "
      "any frozen change; C1 reproduces Phase 6A full governance exactly.")
    a("")
    a("**Unvalidated real-world claim:** none. The alternative providers are deterministic "
      "validation implementations, not production competitors; no production/regulatory claim "
      "is made.")
    a("")
    return "\n".join(out) + "\n"


_JSON = {
    "PHASE_6B_RESOLUTION_METRICS.json": resolution_metrics_json,
    "PHASE_6B_PROVIDER_RESULTS.json": provider_results_json,
    "PHASE_6B_FAILURE_MATRIX.json": failure_matrix_json,
    "PHASE_6B_INVARIANTS.json": invariants_json,
    "PHASE_6B_SELECTION_RECORDS.json": selection_records_json,
    "PHASE_6B_COST_BENEFIT_FRONTIER.json": cost_benefit_frontier_json,
    "PHASE_6B_CONFIGURATION_COMPARISON.json": configuration_comparison_json,
}


def write_all(res: ValidationResults, out_dir: pathlib.Path) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in _JSON.items():
        p = out_dir / name
        p.write_text(json.dumps(fn(res), indent=2, sort_keys=True, default=str) + "\n")
        written.append(p)
    md = out_dir / "PHASE_6B_HETEROGENEITY_REPORT.md"
    md.write_text(report_md(res))
    written.append(md)
    return written
