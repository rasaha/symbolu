"""CLI for internal_policy_controller v3.

    python -m symbolu_neural.internal_policy_controller.v3.cli run [--backend mock|anthropic|mistral]
    python -m symbolu_neural.internal_policy_controller.v3.cli state
    python -m symbolu_neural.internal_policy_controller.v3.cli check   # field-influence self-check only
"""
from __future__ import annotations

import argparse

from . import pilot
from symbolu_neural.internal_policy_controller.v2.data import prompts
from .symbolu_state import compute_state
from .policy import translate


def main() -> None:
    ap = argparse.ArgumentParser(prog="internal_policy_controller.v3")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--backend", default="mock", choices=["mock", "anthropic", "mistral"])
    pr.add_argument("--model", default=None)
    pr.add_argument("--seed", type=int, default=0)
    sub.add_parser("state")
    sub.add_parser("check")
    args = ap.parse_args()

    if args.cmd == "run":
        pilot.print_report(args.seed, args.backend, args.model)
    elif args.cmd == "check":
        fi = pilot.field_influence_check()
        for f, ok in fi.items():
            print(f"{f:16} {'OK' if ok else 'DEFECT'}")
        print("ALL PASS:", all(fi.values()))
    elif args.cmd == "state":
        for p, _para, cat in prompts():
            s = compute_state(p)
            d = translate(s).as_dict()
            print(f"\n[{cat}] {p[:62]}")
            print(f"   state: {s.summary()}  warnings={s.warnings}")
            print(f"   policy: tone={d['tone']} direct={d['directness']} "
                  f"reason={d['reasoning_style']} caution={d['caution']} "
                  f"unc={d['uncertainty_handling']} spec={d['speculation_reduction']}")


if __name__ == "__main__":
    main()
