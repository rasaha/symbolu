"""CLI for internal_policy_controller v3.

    python -m symbolu_neural.internal_policy_controller.v3.cli run [--backend mock|anthropic|mistral]
    python -m symbolu_neural.internal_policy_controller.v3.cli state
    python -m symbolu_neural.internal_policy_controller.v3.cli check   # field-influence self-check only
"""
from __future__ import annotations

import argparse

from . import pilot
from .data import prompts
from .symbolu_state import compute_state
from .policy import translate


def main() -> None:
    ap = argparse.ArgumentParser(prog="internal_policy_controller.v3")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--backend", default="mock", choices=["mock", "anthropic", "mistral"])
    pr.add_argument("--model", default=None)
    pr.add_argument("--seed", type=int, default=0)
    pr.add_argument("--seeds", type=int, default=1,
                    help="number of seeds (0..N-1) to pool with 95%% CIs; >1 => multi-seed report")
    sub.add_parser("state")
    sub.add_parser("check")
    sub.add_parser("coverage")
    args = ap.parse_args()

    if args.cmd == "run":
        if args.seeds > 1:
            pilot.print_multi(pilot.run_multi(args.backend, args.model,
                                              seeds=tuple(range(args.seeds))))
        else:
            pilot.print_report(args.seed, args.backend, args.model)
    elif args.cmd == "check":
        fi = pilot.field_influence_check()
        for f, ok in fi.items():
            print(f"{f:16} {'OK' if ok else 'DEFECT'}")
        print("ALL PASS:", all(fi.values()))
    elif args.cmd == "coverage":
        c = pilot.coverage_report()
        print(f"Signal-value coverage across {c['n_prompts']} prompt-states "
              f"(influences != every value observed):\n")
        print("STATE signals:")
        for k, v in c["state"].items():
            flag = "" if v["n"] >= v["nominal"] else "  <- not all values observed"
            print(f"  {k:12} {v['n']}/{v['nominal']}  {v['seen']}{flag}")
        print("POLICY axes:")
        for a, v in c["axes"].items():
            flag = "" if v["n"] >= v["nominal"] else "  <- not all values observed"
            print(f"  {a:22} {v['n']}/{v['nominal']}{flag}")
        print(f"\nfield-influence (all 6 wired & influencing): {all(c['field_influence'].values())}")
        print("NOTE: RELEASE/anandamaya ('holistic' reasoning_style) is structurally "
              "near-unreachable\n      on natural English text — a phonological-mapper "
              "property, not a wiring defect.\n      Quality run uses DRAFT-states "
              "(model output) x seeds, which broaden coverage further.")
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
