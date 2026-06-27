"""CLI for the internal policy-controller prototype.

    python -m symbolu_neural.internal_policy_controller.cli run
    python -m symbolu_neural.internal_policy_controller.cli drafts   # show example flawed drafts
"""
from __future__ import annotations

import argparse

from . import pilot
from .drafts import make_drafts


def main() -> None:
    ap = argparse.ArgumentParser(prog="internal_policy_controller")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run")
    pr.add_argument("--seed", type=int, default=0)
    sub.add_parser("drafts")
    args = ap.parse_args()

    if args.cmd == "run":
        pilot.print_report(pilot.run(args.seed))
    elif args.cmd == "drafts":
        seen = set()
        for base, draft, flaw in make_drafts():
            if (base, flaw) in seen or base != make_drafts()[0][0]:
                continue
            print(f"[{flaw:11}] {draft}")


if __name__ == "__main__":
    main()
