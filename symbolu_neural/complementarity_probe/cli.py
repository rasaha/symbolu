"""Unified CLI entry point for the Symbol-U complementarity probe.

    python -m symbolu_neural.complementarity_probe.cli exp1   # synonym invariance (all backends)
    python -m symbolu_neural.complementarity_probe.cli exp3   # phonological-vs-semantic dissociation
    python -m symbolu_neural.complementarity_probe.cli exp2 [--u-backend pse_meaning] [--embeddings hf]
    python -m symbolu_neural.complementarity_probe.cli smoke  # quick end-to-end (offline)
    python -m symbolu_neural.complementarity_probe.cli all    # exp1 + exp3 + exp2 smoke
"""
from __future__ import annotations

import argparse

from . import exp1_invariance, exp2_incremental, exp3_dissociation
from .backends import BACKENDS


def main() -> None:
    ap = argparse.ArgumentParser(prog="complementarity_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("exp1", help="synonym invariance, all U backends (offline)")
    p1.add_argument("--n-perm", type=int, default=1000)
    p1.add_argument("--seed", type=int, default=0)

    p3 = sub.add_parser("exp3", help="phonological-vs-semantic dissociation (offline)")
    p3.add_argument("--n-perm", type=int, default=1000)
    p3.add_argument("--seed", type=int, default=0)

    p2 = sub.add_parser("exp2", help="incremental info: E vs E+U vs nulls")
    p2.add_argument("--embeddings", default="hashing", choices=["hashing", "hf"])
    p2.add_argument("--u-backend", default="pse_meaning", choices=BACKENDS)
    p2.add_argument("--model", default=None)
    p2.add_argument("--seed", type=int, default=0)
    p2.add_argument("--l2", type=float, default=1.0)

    sub.add_parser("smoke", help="fast end-to-end check (offline)")
    sub.add_parser("all", help="run exp1 + exp3 + exp2 smoke (offline backend)")

    args = ap.parse_args()

    if args.cmd == "exp1":
        _exp1(exp1_invariance.run(n_perm=args.n_perm, seed=args.seed))
    elif args.cmd == "exp3":
        _exp3(exp3_dissociation.run(n_perm=args.n_perm, seed=args.seed))
    elif args.cmd == "exp2":
        _exp2(exp2_incremental.run(backend=args.embeddings, model_name=args.model,
                                   u_backend=args.u_backend, l2=args.l2, seed=args.seed))
    elif args.cmd == "smoke":
        print(">> exp1 (fast permutation, all backends)")
        _exp1(exp1_invariance.run(n_perm=200))
        print("\n>> exp3 (dissociation, fast)")
        _exp3(exp3_dissociation.run(n_perm=200))
        print("\n>> exp2 (hashing backend, pipeline only)")
        _exp2(exp2_incremental.run(backend="hashing", u_backend="pse_meaning"))
        print("\nSMOKE OK — harness runs end to end across all backends.")
    elif args.cmd == "all":
        _exp1(exp1_invariance.run())
        print()
        _exp3(exp3_dissociation.run())
        print()
        _exp2(exp2_incremental.run(u_backend="pse_meaning"))


def _exp1(r):
    print(f"[exp1] groups={r['n_groups']} words={r['n_words']}  "
          f"(phon_null index={r['phonological_null']['index']:+.3f})")
    for name, b in r["backends"].items():
        print(f"  {name:<15} index={b['index']:+.3f}  p={b['p_value']:.4f}  dim={b['dim']}")


def _exp3(r):
    print("[exp3] semantic(synonyms) vs phonological(rhymes) invariance:")
    for name, b in r["backends"].items():
        print(f"  {name:<15} sem={b['semantic_index']:+.3f}  "
              f"phon={b['phonological_index']:+.3f}  dissoc={b['dissociation']:+.3f}")


def _exp2(r):
    base, eu = r["E"], r["E+U"]
    nulls = [k for k in r if k.startswith("E+") and k != "E+U"]
    best_null = max(r[k] for k in nulls) if nulls else 0.0
    print(f"[exp2] E={r['backend']} U={r['u_backend']} semantic={r['is_semantic']}  "
          f"E={base:.3f}  E+U={eu:.3f}  best_null={best_null:.3f}  ΔU={eu - base:+.3f}")


if __name__ == "__main__":
    main()
