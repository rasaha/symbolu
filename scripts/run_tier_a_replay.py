#!/usr/bin/env python3
"""Run the pre-registered Tier-A detector over partner Prometheus/HPA exports (Track B).

Pipeline (all offline, read-only): partner export → `PartnerPrometheusAdapter` →
`detect_tier_a` (per-cluster Tier-A candidates + Tier-B events) → `compute_apcy`
(fleet roll-up with the pre-registered honesty trip-wire) → SRE-adjudication
worksheets. The detector + cost model are frozen in
`Project_documentation/governance/docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md`.

Modes
-----
- **default (no args):** run on the committed synthetic schema fixture and write a
  clearly-labelled TOOLING SELF-TEST artifact. Produces NO market number — the APCY
  trip-wire refuses the fixture as evidence by design.
- **--manifest FILE.json:** run real partner exports. JSON list of:
    {"metrics": "...csv", "incidents": "...csv"|null, "cluster": "...", "org": "...",
     "dollars_per_replica_hour": 0.10|null, "dollars_per_incident_minute": 5.0|null,
     "latency_slo_seconds": 1.0}
  Every number emitted is labelled `real-trace-replay (estimate pending live
  adjudication)` and is gated on SRE adjudication before it counts.

Usage
-----
    python scripts/run_tier_a_replay.py
    python scripts/run_tier_a_replay.py --manifest partners.json --out-dir artifacts/...
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from cloud_controller.replay.adapters import PartnerPrometheusAdapter  # noqa: E402
from cloud_controller.replay.tier_a import (  # noqa: E402
    compute_apcy,
    detect_tier_a,
    emit_worksheets,
)

FIX = os.path.join(REPO, "data", "cloud_traces", "fixtures")
DEFAULT_OUT = os.path.join(REPO, "artifacts", "cloud_controller_real_validation")


def _entries_from_manifest(path):
    with open(path) as f:
        return json.load(f)


def _fixture_entry():
    return [{
        "metrics": os.path.join(FIX, "partner_prometheus_SCHEMA_FIXTURE.csv"),
        "incidents": os.path.join(FIX, "partner_incidents_SCHEMA_FIXTURE.csv"),
        "cluster": "fixture-cluster", "org": "fixture-org",
        "dollars_per_replica_hour": 0.10, "dollars_per_incident_minute": 5.0,
        "latency_slo_seconds": 1.0,
    }]


def run_entry(e):
    series = PartnerPrometheusAdapter().load(
        e["metrics"], incidents_path=e.get("incidents"),
        cluster=e.get("cluster"), org=e.get("org"),
        latency_slo_seconds=e.get("latency_slo_seconds", 1.0),
        queue_capacity=e.get("queue_capacity"),
    )
    return detect_tier_a(
        series, cluster=e.get("cluster"), org=e.get("org"),
        dollars_per_replica_hour=e.get("dollars_per_replica_hour"),
        dollars_per_incident_minute=e.get("dollars_per_incident_minute"),
    )


def build_markdown(results, apcy, is_fixture):
    L = []
    title = "Tier-A replay — TOOLING SELF-TEST (synthetic fixture)" if is_fixture \
        else "Tier-A replay — design-partner exports"
    L.append(f"# {title}")
    L.append("")
    L.append(f"> **Label: `{apcy.label}`.** Detector + cost model are frozen in "
             "`Project_documentation/governance/docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md`. The replay "
             "surfaces Tier-A **candidates**; an SRE confirms true/false + cost before "
             "anything counts. **Tier-B is never market evidence.**")
    if is_fixture:
        L.append("")
        L.append("> ⚠️ **This is a synthetic schema fixture — a tooling self-test, NOT a "
                 "market number.** The coverage trip-wire below refuses it as evidence "
                 "by design. Real numbers require real partner data + SRE adjudication.")
    L.append("")
    L.append("## Per-cluster Tier-A counts")
    L.append("")
    L.append("| org | cluster | cluster-months | cycles H/N/NH | Tier-A candidates | Tier-B (diagnostic) |")
    L.append("|---|---|--:|--:|--:|--:|")
    for r in results:
        L.append(f"| {r.org} | `{r.cluster}` | {r.cluster_months:.3f} | "
                 f"{r.cycles_helping}/{r.cycles_neutral}/{r.cycles_not_helping} | "
                 f"{r.n_tier_a} | {r.n_tier_b} |")
    L.append("")
    L.append("## APCY (fleet roll-up) — with the pre-registered honesty gate")
    L.append("")
    a = apcy
    # Honesty: do NOT print a market-looking APCY figure we have just declared
    # non-evidence. Withhold it unless the pre-registered coverage floor is met.
    if not a.reportable:
        apcy_str = "**WITHHELD** — not reportable as market evidence (see reason)"
    elif a.apcy_usd_per_cluster_year is not None:
        apcy_str = f"${a.apcy_usd_per_cluster_year:,.0f}/cluster-yr"
    else:
        apcy_str = "pending partner cost input"
    L.append(f"- orgs: **{a.n_orgs}** · clusters: **{a.n_clusters}** · coverage: "
             f"**{a.total_cluster_months:.2f} cluster-months**")
    L.append(f"- Tier-A candidates: **{a.total_tier_a_candidates}** · Tier-B events: "
             f"{a.total_tier_b_events}")
    L.append(f"- **APCY:** {apcy_str}")
    L.append(f"- **reportable as market evidence: {a.reportable}** · market-red: {a.market_red}")
    L.append(f"- reason: {a.reason}")
    L.append("")
    L.append("## SRE-adjudication worksheets")
    L.append("")
    L.append("_One per Tier-A candidate. Full template: "
             "`docs/cloud_scaling_real_validation/track_c_design_partner/"
             "04_SRE_ADJUDICATION_WORKSHEET.md`._")
    L.append("")
    for r in results:
        L.append(emit_worksheets(r))
        L.append("")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description="Pre-registered Tier-A replay over partner exports.")
    p.add_argument("--manifest", help="JSON manifest of partner cluster exports.")
    p.add_argument("--out-dir", default=DEFAULT_OUT)
    args = p.parse_args(argv)

    is_fixture = args.manifest is None
    entries = _fixture_entry() if is_fixture else _entries_from_manifest(args.manifest)
    results = [run_entry(e) for e in entries]
    apcy = compute_apcy(results)

    os.makedirs(args.out_dir, exist_ok=True)
    stem = "tier_a_selftest.STUB_EXAMPLE" if is_fixture else "tier_a_partner_replay"
    md_path = os.path.join(args.out_dir, f"{stem}.md")
    json_path = os.path.join(args.out_dir, f"{stem}.json")

    with open(md_path, "w") as f:
        f.write(build_markdown(results, apcy, is_fixture))
    with open(json_path, "w") as f:
        json.dump({
            "label": apcy.label,
            "is_tooling_self_test": is_fixture,
            "spec_doc": "Project_documentation/governance/docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md",
            "clusters": [r.to_dict() for r in results],
            "apcy": apcy.to_dict(),
        }, f, indent=2)

    print(f"clusters: {len(results)} | Tier-A candidates: {apcy.total_tier_a_candidates} | "
          f"reportable: {apcy.reportable} | market_red: {apcy.market_red}")
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    if is_fixture:
        print("NOTE: fixture self-test — NOT market evidence (trip-wire refuses it by design).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
