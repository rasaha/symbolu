"""Experiment 1 — Synonym invariance of Symbol-U (no LLM, fully offline).

The cheapest kill switch (SYMBOL_U_RESEARCH_STRATEGY.md §8.1). The patent claims
Symbol-U is a *semantic* coordinate system. If so, synonyms (same meaning,
different sound) should map to SIMILAR `U` vectors. If `U` is really phonological
(a function of sound), synonyms will scatter.

We measure the between-vs-within invariance index over curated synonym groups,
with a permutation p-value, and compare the Symbol-U Vritti vector against the
raw phonological (SoundClass) null. No model, no GPU, no network.

Decision (pre-registered):
  index ≈ 0 (synonyms scatter)  -> FAIL: U is phonological, not semantic. STOP/PIVOT.
  index >> 0 and p small        -> synonyms cluster: U carries meaning-aligned signal.

Run:  python -m symbolu_neural.complementarity_probe.exp1_invariance
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List

import numpy as np

from .symbolu_engine import SymbolUEngine
from .nulls import phonological_features
from .metrics import invariance_index, invariance_permutation_p

DATA = os.path.join(os.path.dirname(__file__), "data", "synonyms.jsonl")


def load_groups(path: str = DATA):
    groups = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                groups.append(json.loads(line))
    return groups


def run(path: str = DATA, n_perm: int = 2000, seed: int = 0) -> dict:
    eng = SymbolUEngine()
    groups = load_groups(path)

    # Symbol-U Vritti vector per word, grouped by concept.
    u_groups: List[np.ndarray] = []
    ph_groups: List[np.ndarray] = []
    for g in groups:
        words = g["words"]
        u_groups.append(np.stack([np.asarray(eng.vritti_vec(w)) for w in words]))
        ph_groups.append(phonological_features(words))

    u_idx = invariance_index(u_groups)
    u_perm = invariance_permutation_p(u_groups, n_perm=n_perm, seed=seed)
    ph_idx = invariance_index(ph_groups)

    return {
        "n_groups": len(groups),
        "n_words": sum(len(g["words"]) for g in groups),
        "symbolu_vritti": {**u_idx, **u_perm},
        "phonological_null": ph_idx,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--n-perm", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    r = run(args.data, n_perm=args.n_perm, seed=args.seed)
    u = r["symbolu_vritti"]
    ph = r["phonological_null"]

    print("=" * 64)
    print("EXP1 — Synonym invariance of Symbol-U (Vritti)  [no LLM, offline]")
    print("=" * 64)
    print(f"groups={r['n_groups']}  words={r['n_words']}")
    print(f"\nSymbol-U Vritti:   within={u['within']:.3f}  between={u['between']:.3f}"
          f"  index={u['index']:+.3f}  p={u['p_value']:.4f}")
    print(f"Phonological null: within={ph['within']:.3f}  between={ph['between']:.3f}"
          f"  index={ph['index']:+.3f}")

    print("\n----------------------------- VERDICT ------------------------------")
    idx, p = u["index"], u["p_value"]
    if idx < 0.05 or p > 0.05:
        print("FAIL (as the strategy memo predicts): synonyms do NOT cluster in")
        print("Symbol-U space. The Vritti vector is a function of SOUND, not")
        print("meaning — synonyms with different phonology get different U.")
        print("Gate-0 (semantic validity) is not cleared on this premise alone.")
        print("Per SYMBOL_U_RESEARCH_STRATEGY.md this is the cheap, clean negative:")
        print("U is phonological, not semantic. STOP or PIVOT to phonology.")
    else:
        print("PASS: synonyms cluster in Symbol-U space above chance — U carries")
        print("meaning-aligned structure. Proceed to exp2 (incremental info vs E).")
    print("(Reference: the phonological null's index bounds what pure sound gives;")
    print(" if Symbol-U ≈ phonological null, the Vritti ontology adds nothing over")
    print(" raw sound structure.)")


if __name__ == "__main__":
    main()
