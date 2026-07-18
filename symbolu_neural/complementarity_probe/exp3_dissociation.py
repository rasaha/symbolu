"""Experiment 3 — Phonological vs semantic dissociation (no LLM, offline).

SYMBOL_U_RESEARCH_STRATEGY.md §8.4. The decisive question for the patent's thesis
is not "does U have ANY structure" but "is that structure SEMANTIC or merely
phonological?" We give each U backend two contrasting groupings of words:

  - SEMANTIC groups  (synonyms.jsonl): same MEANING, different SOUND.
  - PHONOLOGICAL groups (rhymes.jsonl): same SOUND (rhyme), different MEANING.

For a backend, the invariance index on each grouping says which axis it tracks:

  semantic_index  high, phonological_index low  -> SEMANTIC encoder (the claim)
  phonological_index high, semantic_index low   -> PHONOLOGICAL encoder (the trap)

dissociation = semantic_index - phonological_index.
  > 0 : leans semantic.   < 0 : leans phonological (tracks sound, not meaning).

Run:  python -m symbolu_neural.complementarity_probe.exp3_dissociation
"""
from __future__ import annotations

import argparse
import os
from typing import List

import numpy as np

from .backends import get_backend, BACKENDS
from .metrics import invariance_index, invariance_permutation_p
from .exp1_invariance import load_groups

SYN = os.path.join(os.path.dirname(__file__), "data", "synonyms.jsonl")
RHY = os.path.join(os.path.dirname(__file__), "data", "rhymes.jsonl")


def _index_for(groups, backend, n_perm, seed):
    g_vecs: List[np.ndarray] = [
        np.stack([np.asarray(backend.encode(w)) for w in g["words"]]) for g in groups
    ]
    idx = invariance_index(g_vecs)
    perm = invariance_permutation_p(g_vecs, n_perm=n_perm, seed=seed)
    return {**idx, **perm}


def run(syn_path=SYN, rhy_path=RHY, backends=None, n_perm=1000, seed=0) -> dict:
    backends = backends or BACKENDS
    syn = load_groups(syn_path)
    rhy = load_groups(rhy_path)
    out = {"n_syn_groups": len(syn), "n_rhy_groups": len(rhy), "backends": {}}
    for name in backends:
        b = get_backend(name)
        s = _index_for(syn, b, n_perm, seed)
        p = _index_for(rhy, b, n_perm, seed)
        out["backends"][name] = {
            "dim": b.dim,
            "semantic_index": s["index"], "semantic_p": s["p_value"],
            "phonological_index": p["index"], "phonological_p": p["p_value"],
            "dissociation": s["index"] - p["index"],
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backends", nargs="*", default=None, choices=BACKENDS)
    ap.add_argument("--n-perm", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    r = run(backends=args.backends, n_perm=args.n_perm, seed=args.seed)

    print("=" * 76)
    print("EXP3 — Phonological vs semantic dissociation  [no LLM, offline]")
    print("=" * 76)
    print(f"semantic groups (synonyms)={r['n_syn_groups']}  "
          f"phonological groups (rhymes)={r['n_rhy_groups']}\n")
    print(f"{'backend':<16}{'sem_idx':>9}{'sem_p':>8}{'phon_idx':>10}{'phon_p':>8}"
          f"{'dissoc':>9}  leans")
    print("-" * 76)
    for name, b in r["backends"].items():
        lean = "SEMANTIC" if b["dissociation"] > 0.01 else (
            "phonological" if b["dissociation"] < -0.01 else "neither")
        print(f"{name:<16}{b['semantic_index']:>+9.3f}{b['semantic_p']:>8.3f}"
              f"{b['phonological_index']:>+10.3f}{b['phonological_p']:>8.3f}"
              f"{b['dissociation']:>+9.3f}  {lean}")

    print("\n------------------------------- VERDICT --------------------------------")
    for name, b in r["backends"].items():
        if b["phonological_index"] > b["semantic_index"] + 0.01:
            print(f"- {name}: clusters RHYMES more than synonyms "
                  f"({b['phonological_index']:+.3f} > {b['semantic_index']:+.3f}) "
                  f"-> tracks SOUND, not meaning.")
        elif b["semantic_index"] > b["phonological_index"] + 0.01:
            print(f"- {name}: clusters SYNONYMS more than rhymes "
                  f"({b['semantic_index']:+.3f} > {b['phonological_index']:+.3f}) "
                  f"-> leans semantic.")
        else:
            print(f"- {name}: no clear dissociation (both indices ~equal, near 0).")


if __name__ == "__main__":
    main()
