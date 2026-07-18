"""CLI for the API control-protocol pilot.

    python -m symbolu_neural.api_control_protocol.cli run [--backend mock|anthropic]
    python -m symbolu_neural.api_control_protocol.cli packets   # print each arm's control message
    python -m symbolu_neural.api_control_protocol.cli tokens    # token-cost table only (offline, real)
"""
from __future__ import annotations

import argparse

from . import pilot
from .packets import ARMS, build, approx_tokens
from .ontology import AXES


def main() -> None:
    ap = argparse.ArgumentParser(prog="api_control_protocol")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--backend", default="mock", choices=["mock", "anthropic", "mistral"])
    pr.add_argument("--model", default=None)
    sub.add_parser("packets")
    sub.add_parser("tokens")
    args = ap.parse_args()

    if args.cmd == "run":
        pilot.print_report(pilot.run(args.backend, args.model))
    elif args.cmd == "packets":
        for arm in ARMS:
            print(f"\n{'='*70}\nARM: {arm}   (axis=calm)\n{'='*70}")
            print(build(arm, "calm") or "(empty — no control)")
    elif args.cmd == "tokens":
        print(f"{'arm':<18}{'ctrl_tokens (axis-avg, approx)':>32}")
        print("-" * 50)
        for arm in ARMS:
            avg = sum(approx_tokens(build(arm, a)) for a in AXES) / len(AXES)
            print(f"{arm:<18}{avg:>32.0f}")


if __name__ == "__main__":
    main()
