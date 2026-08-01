"""Command-line interface for the sequence-risk analyzer.

All output is JSON. Exit code is non-zero when any ESCALATE (or UNAVAILABLE)
finding is produced, so the CLI composes into pipelines and CI checks.

Commands
--------
  run <events.jsonl> [--spec NAME ...] [--policy]
      Feed a JSONL event stream; print findings + the integrity run-report. With
      --policy, also print the authoritative policy consequence per finding.
  ontologies                 list ontologies + recipe refs
  specs                      list the available assembly key specs
  demo <firearm|exfiltration|benign|approved_export>
  eval                       run the evaluation harness (marks NOT RUN honestly)
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, policy as policy_mod, signals
from .analyzer import SequenceRiskAnalyzer
from .linkage import (
    BY_ACTOR, BY_ACTOR_TARGET, BY_CASE, BY_CORRELATION, BY_TARGET,
)
from .recipes import DIGITAL_ONTOLOGY, ONTOLOGIES

_SPECS = {"by_actor": BY_ACTOR, "by_case": BY_CASE, "by_target": BY_TARGET,
          "by_actor_target": BY_ACTOR_TARGET, "by_correlation": BY_CORRELATION}


def _emit(obj) -> None:
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def _load_jsonl(path: str) -> list[dict]:
    events = []
    with open(path, "r", encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"line {n}: invalid JSON: {exc}")
    return events


def _run(events, ontology, specs, with_policy, providers=None) -> int:
    az = SequenceRiskAnalyzer(ontology, specs=specs, providers=providers)
    findings = []
    for ev in events:
        findings.extend(f.to_dict() for f in az.observe(ev))
    escs = [f for f in findings
            if f["signal"] in (signals.ESCALATE, signals.UNAVAILABLE)]
    out = {"ontology": ontology.ontology_id, "ontology_version": ontology.version,
           "finding_count": len(findings), "escalation_count": len(escs),
           "findings": findings, "run_report": az.report.to_dict()}
    if with_policy:
        out["policy_consequences"] = policy_mod.decide_batch(findings)
    _emit(out)
    return 1 if escs else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="composite_threat_detector",
        description="Composite Capability & Sequence-Risk Analyzer (advisory)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="feed a JSONL event stream")
    r.add_argument("events")
    r.add_argument("--ontology", default=DIGITAL_ONTOLOGY.ontology_id)
    r.add_argument("--spec", action="append", choices=sorted(_SPECS),
                   help="assembly key spec(s); repeatable (default by_case+by_actor)")
    r.add_argument("--policy", action="store_true",
                   help="also print authoritative policy consequences")

    sub.add_parser("ontologies", help="list ontologies + recipes")
    sub.add_parser("specs", help="list assembly key specs")
    sub.add_parser("eval", help="run the synthetic-corpus evaluation")
    sub.add_parser("manifest", help="print the corpus manifest")
    fr = sub.add_parser("freeze", help="print the pre-evaluation freeze")
    fr.add_argument("--commit", default="UNSET")
    sub.add_parser("readiness", help="run historical-replay readiness gates H1-H8")
    bn = sub.add_parser("bench", help="synthetic operational load benchmark")
    bn.add_argument("--profile", default="balanced")
    bn.add_argument("--scale", type=int, default=50)
    al = sub.add_parser("alerts", help="alert-volume + review-burden report")
    al.add_argument("--profile", default="enterprise_like")
    al.add_argument("--scale", type=int, default=200)
    rv = sub.add_parser("review", help="operator-review simulation")
    rv.add_argument("--profile", default="enterprise_like")
    rv.add_argument("--scale", type=int, default=200)

    d = sub.add_parser("demo", help="run a built-in illustration")
    d.add_argument("which", choices=["firearm", "exfiltration", "benign",
                                     "approved_export"])

    args = p.parse_args(argv)

    if args.cmd == "ontologies":
        _emit({oid: {"version": o.version,
                     "recipes": [{"ref": rr.ref, "name": rr.name,
                                  "required": sorted(rr.required),
                                  "optional": sorted(rr.optional),
                                  "severity": rr.severity,
                                  "recommended_consequence": rr.recommended_consequence}
                                 for rr in o.recipes]}
               for oid, o in ONTOLOGIES.items()})
        return 0

    if args.cmd == "specs":
        _emit({name: {"ref": s.ref, "dims": list(s.dims)}
               for name, s in _SPECS.items()})
        return 0

    if args.cmd == "eval":
        from evaluation import harness
        _emit(harness.evaluate())
        return 0

    if args.cmd == "manifest":
        from evaluation import corpus
        _emit(corpus.manifest())
        return 0

    if args.cmd == "freeze":
        from evaluation import corpus
        _emit(corpus.freeze(code_commit=args.commit))
        return 0

    if args.cmd == "readiness":
        from evaluation import readiness
        rep = readiness.run()
        _emit(rep)
        return 0 if rep["verdict"].startswith("CONTINUE") else 1

    if args.cmd == "bench":
        from evaluation import benchmark
        _emit(benchmark.run_load(args.profile, scale=args.scale))
        return 0

    if args.cmd == "alerts":
        from evaluation import alerts
        _emit(alerts.alert_volume(args.profile, scale=args.scale))
        return 0

    if args.cmd == "review":
        from evaluation import review_sim
        _emit(review_sim.simulate(args.profile, scale=args.scale))
        return 0

    if args.cmd == "demo":
        from demos import scenarios
        from .providers import FixtureProvider, ProviderRegistry
        from .recipes import PHYSICAL_FIREARM_ONTOLOGY
        # approved_export illustrates neutralization by a TRUSTED, verified record
        export_provider = ProviderRegistry(providers=(FixtureProvider(
            "demo-trusted", "1.0.0", [{"record_id": "CHG-771",
             "tag": "compliance_export", "tenant": "acme", "workflow": "wf-exp",
             "actor": "*", "target_family": "*", "operations": "*",
             "destinations": "*", "environment": "*", "tools": "*",
             "approver_identity": "user://dpo",
             "approver_authority": "data_protection_officer"}]),))
        table = {
            "firearm": (PHYSICAL_FIREARM_ONTOLOGY, scenarios.firearm_events,
                        (BY_CORRELATION,), None),
            "exfiltration": (DIGITAL_ONTOLOGY, scenarios.exfiltration_events,
                             (BY_CASE,), None),
            "benign": (DIGITAL_ONTOLOGY, scenarios.benign_migration_events,
                       (BY_CASE,), None),
            "approved_export": (DIGITAL_ONTOLOGY, scenarios.approved_export_events,
                                (BY_CASE,), export_provider),
        }
        ont, evs, specs, providers = table[args.which]
        return _run(evs, ont, specs, with_policy=True, providers=providers)

    if args.cmd == "run":
        ontology = ONTOLOGIES.get(args.ontology)
        if ontology is None:
            raise SystemExit(f"unknown ontology {args.ontology!r}; "
                             f"choose from {sorted(ONTOLOGIES)}")
        specs = tuple(_SPECS[s] for s in args.spec) if args.spec else (BY_CASE, BY_ACTOR)
        return _run(_load_jsonl(args.events), ontology, specs, args.policy)

    return 0


if __name__ == "__main__":
    sys.exit(main())
