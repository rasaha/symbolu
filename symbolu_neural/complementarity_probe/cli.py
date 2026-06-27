"""Unified CLI entry point for the Symbol-U complementarity probe.

    python -m symbolu_neural.complementarity_probe.cli exp1
    python -m symbolu_neural.complementarity_probe.cli exp2 [--embeddings hf]
    python -m symbolu_neural.complementarity_probe.cli smoke   # quick end-to-end
    python -m symbolu_neural.complementarity_probe.cli all
"""
from __future__ import annotations

import argparse

from . import exp1_invariance, exp2_incremental


def main() -> None:
    ap = argparse.ArgumentParser(prog="complementarity_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("exp1", help="synonym invariance (no LLM, offline)")
    p1.add_argument("--n-perm", type=int, default=2000)
    p1.add_argument("--seed", type=int, default=0)

    p2 = sub.add_parser("exp2", help="incremental info: E vs E+U vs nulls")
    p2.add_argument("--embeddings", default="hashing", choices=["hashing", "hf"])
    p2.add_argument("--model", default=None)
    p2.add_argument("--seed", type=int, default=0)
    p2.add_argument("--l2", type=float, default=1.0)

    ps = sub.add_parser("smoke", help="fast end-to-end check (offline)")
    pa = sub.add_parser("all", help="run exp1 then exp2 (offline backend)")

    args = ap.parse_args()

    if args.cmd == "exp1":
        r = exp1_invariance.run(n_perm=args.n_perm, seed=args.seed)
        _print_exp1(r)
    elif args.cmd == "exp2":
        r = exp2_incremental.run(backend=args.embeddings, model_name=args.model,
                                 l2=args.l2, seed=args.seed)
        _print_exp2(r)
    elif args.cmd == "smoke":
        print(">> exp1 (fast permutation)")
        _print_exp1(exp1_invariance.run(n_perm=200))
        print("\n>> exp2 (hashing backend, pipeline only)")
        _print_exp2(exp2_incremental.run(backend="hashing"))
        print("\nSMOKE OK — harness runs end to end.")
    elif args.cmd == "all":
        _print_exp1(exp1_invariance.run())
        print()
        _print_exp2(exp2_incremental.run())


def _print_exp1(r):
    u = r["symbolu_vritti"]
    print(f"[exp1] groups={r['n_groups']} words={r['n_words']}  "
          f"index={u['index']:+.3f}  p={u['p_value']:.4f}  "
          f"(phonological_null index={r['phonological_null']['index']:+.3f})")


def _print_exp2(r):
    base, eu = r["E"], r["E+U"]
    nulls = [k for k in r if k.startswith("E+") and k != "E+U"]
    best_null = max(r[k] for k in nulls) if nulls else 0.0
    print(f"[exp2] backend={r['backend']} semantic={r['is_semantic']}  "
          f"E={base:.3f}  E+U={eu:.3f}  best_null={best_null:.3f}  "
          f"ΔU={eu - base:+.3f}")


if __name__ == "__main__":
    main()
