"""CLI for the controllability pilot.

    python -m symbolu_neural.controllability_pilot.cli run   [--u-backend pse_meaning]
    python -m symbolu_neural.controllability_pilot.cli smoke              # fast, tiny
    python -m symbolu_neural.controllability_pilot.cli samples            # print examples
"""
from __future__ import annotations

import argparse

from . import pilot
from .data import AXES, make_corpus, prompts
from .codes import build_all
from .generator import Vocab, train_model, generate


def main() -> None:
    ap = argparse.ArgumentParser(prog="controllability_pilot")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="full pilot run")
    pr.add_argument("--u-backend", default="pse_meaning")
    pr.add_argument("--per-axis", type=int, default=60)
    pr.add_argument("--steps", type=int, default=400)
    pr.add_argument("--n-seeds", type=int, default=4)
    pr.add_argument("--json", default=None)

    sub.add_parser("smoke", help="fast tiny run (pipeline check)")
    ps = sub.add_parser("samples", help="print example generations per arm/axis")
    ps.add_argument("--u-backend", default="pse_meaning")

    args = ap.parse_args()
    if args.cmd == "run":
        r = pilot.run(per_axis=args.per_axis, u_backend=args.u_backend,
                      steps=args.steps, n_seeds=args.n_seeds)
        if args.json:
            import json
            with open(args.json, "w") as f:
                json.dump(r, f, indent=2)
        pilot.print_report(r)
    elif args.cmd == "smoke":
        r = pilot.run(per_axis=20, steps=120, n_seeds=2)
        pilot.print_report(r)
        print("\nSMOKE OK — pipeline runs end to end (results not meaningful at this size).")
    elif args.cmd == "samples":
        _samples(args.u_backend)


def _samples(u_backend: str) -> None:
    corpus = make_corpus(per_axis=40)
    vocab = Vocab([t for t, _ in corpus], extra=AXES + prompts())
    codes = build_all(corpus, u_backend=u_backend)
    su = codes["symbolu"]
    dim = len(next(iter(su.values())))
    model = train_model(corpus, vocab, codes=su, code_dim=dim, steps=300)
    print(f"Example Symbol-U-conditioned generations (u_backend={u_backend}):")
    for a in AXES:
        print(f"\n[target axis = {a}]")
        for p in ["the", "a", "they"]:
            print(f"   {p!r:6} -> {generate(model, vocab, p, su[a], max_len=12, seed=1)}")


if __name__ == "__main__":
    main()
