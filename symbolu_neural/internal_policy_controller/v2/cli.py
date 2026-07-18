"""CLI for internal_policy_controller v2.

    python -m symbolu_neural.internal_policy_controller.v2.cli run [--backend mock|anthropic|mistral]
    python -m symbolu_neural.internal_policy_controller.v2.cli state    # show Symbol-U state + policy per prompt
"""
from __future__ import annotations

import argparse
import sys

from . import pilot
from .data import prompts
from .symbolu_state import compute_state
from .policy import translate

_DEPRECATION = (
    "\n*** DEPRECATED: this is v2 — SUPERSEDED with known wiring defects (only "
    "Guna+Valence reached policy, Aspect missing, dead branches; see "
    "V2_WIRING_AUDIT.md). Do NOT use for scientific conclusions. Canonical version "
    "is v3: python -m symbolu_neural.internal_policy_controller.v3.cli ***\n")


def main() -> None:
    print(_DEPRECATION, file=sys.stderr)
    ap = argparse.ArgumentParser(prog="internal_policy_controller.v2")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--backend", default="mock", choices=["mock", "anthropic", "mistral"])
    pr.add_argument("--model", default=None)
    pr.add_argument("--seed", type=int, default=0)
    sub.add_parser("state")
    args = ap.parse_args()

    if args.cmd == "run":
        pilot.print_report(args.seed, args.backend, args.model)
    elif args.cmd == "state":
        for p, _para, cat in prompts():
            s = compute_state(p)
            pol = translate(s).as_dict()
            print(f"\n[{cat}] {p[:64]}")
            print(f"   state: {s.summary()}")
            print(f"   policy: tone={pol['tone']} caution={pol['caution']} "
                  f"direct={pol['directness']} spec_red={pol['speculation_reduction']}")


if __name__ == "__main__":
    main()
