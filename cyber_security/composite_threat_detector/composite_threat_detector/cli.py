"""Command-line interface for the composite-threat detector.

All output is JSON. Exit code is non-zero when any ESCALATE finding is produced,
so the CLI composes into pipelines and CI checks.

Commands
--------
  run <events.jsonl> [--ontology ID] [--window N] [--standing]
      Feed a JSONL stream of events (one event per line) through the monitor and
      print the findings. ``--standing`` prints the final standing findings per
      correlation instead of the edge-triggered stream.

  ontologies
      List the available ontologies and their recipes.

  demo <firearm|exfiltration>
      Run a built-in scenario.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .monitor import CompositeThreatMonitor
from .recipes import DIGITAL_ONTOLOGY, ONTOLOGIES


def _load_jsonl(path: str) -> list[dict]:
    events = []
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"line {line_no}: invalid JSON: {exc}")
    return events


def _emit(obj) -> None:
    print(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def _run(events, ontology, window, standing) -> int:
    mon = CompositeThreatMonitor(ontology, window_actions=window)
    findings = []
    if standing:
        seen_cids = []
        for ev in events:
            mon.observe(ev)
            cid = str(ev.get("correlation_id"))
            if cid not in seen_cids:
                seen_cids.append(cid)
        for cid in seen_cids:
            findings.extend(f.to_dict() for f in mon.standing_findings(cid))
    else:
        for ev in events:
            findings.extend(f.to_dict() for f in mon.observe(ev))
    escalations = [f for f in findings if f["signal"] == "ESCALATE"]
    _emit({"ontology": ontology.ontology_id, "ontology_version": ontology.version,
           "finding_count": len(findings), "escalation_count": len(escalations),
           "findings": findings})
    return 1 if escalations else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="composite_threat_detector",
                                description="advisory composite-threat assembly detector")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="feed a JSONL event stream")
    r.add_argument("events")
    r.add_argument("--ontology", default=DIGITAL_ONTOLOGY.ontology_id)
    r.add_argument("--window", type=int, default=None)
    r.add_argument("--standing", action="store_true")

    sub.add_parser("ontologies", help="list ontologies + recipes")

    d = sub.add_parser("demo", help="run a built-in scenario")
    d.add_argument("which", choices=["firearm", "exfiltration"])

    args = p.parse_args(argv)

    if args.cmd == "ontologies":
        _emit({oid: {"version": o.version,
                     "recipes": [{"recipe_id": rr.recipe_id, "name": rr.name,
                                  "required": sorted(rr.required),
                                  "optional": sorted(rr.optional)}
                                 for rr in o.recipes]}
               for oid, o in ONTOLOGIES.items()})
        return 0

    if args.cmd == "demo":
        from demos import scenarios
        if args.which == "firearm":
            from .recipes import PHYSICAL_FIREARM_ONTOLOGY
            return _run(scenarios.firearm_events, PHYSICAL_FIREARM_ONTOLOGY, None, False)
        return _run(scenarios.exfiltration_events, DIGITAL_ONTOLOGY, None, False)

    if args.cmd == "run":
        ontology = ONTOLOGIES.get(args.ontology)
        if ontology is None:
            raise SystemExit(f"unknown ontology {args.ontology!r}; "
                             f"choose from {sorted(ONTOLOGIES)}")
        return _run(_load_jsonl(args.events), ontology, args.window, args.standing)

    return 0


if __name__ == "__main__":
    sys.exit(main())
