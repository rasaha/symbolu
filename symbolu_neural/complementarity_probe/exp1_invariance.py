"""Experiment 1 — Synonym invariance of Symbol-U, per backend (no LLM, offline).

The cheapest kill switch (SYMBOL_U_RESEARCH_STRATEGY.md §8.1). The patent claims
Symbol-U is a *semantic* coordinate system. If so, synonyms (same meaning,
different sound) should map to SIMILAR `U` vectors. If `U` is really phonological
(a function of sound), synonyms scatter.

We compute the between-vs-within invariance index over curated synonym groups,
with a permutation p-value, for EVERY U backend (vritti_mapper, pse_meaning,
pse_resonance, combined) plus the raw phonological (SoundClass) null. The whole
point of adding the PSE backends is to test whether the phoneme->MEANING layer
makes `U` more synonym-invariant than the vritti_mapper approximation.

Decision (pre-registered):
  index ≈ 0 (synonyms scatter)  -> FAIL: U is phonological, not semantic.
  index >> 0 and p small        -> synonyms cluster: U carries meaning-aligned signal.

Run:  python -m symbolu_neural.complementarity_probe.exp1_invariance
      python -m symbolu_neural.complementarity_probe.exp1_invariance --backends pse_meaning
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List

import numpy as np

from .backends import get_backend, BACKENDS
from .nulls import phonological_features
from .metrics import invariance_index, invariance_permutation_p

DATA = os.path.join(os.path.dirname(__file__), "data", "synonyms.jsonl")


def load_groups(path: str):
    groups = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                groups.append(json.loads(line))
    return groups


def backend_index(groups, backend_name: str, n_perm: int, seed: int) -> dict:
    b = get_backend(backend_name)
    g_vecs: List[np.ndarray] = []
    for g in groups:
        g_vecs.append(np.stack([np.asarray(b.encode(w)) for w in g["words"]]))
    idx = invariance_index(g_vecs)
    perm = invariance_permutation_p(g_vecs, n_perm=n_perm, seed=seed)
    return {"dim": b.dim, **idx, **perm}


def run(path: str = DATA, backends=None, n_perm: int = 1000, seed: int = 0) -> dict:
    backends = backends or BACKENDS
    groups = load_groups(path)
    out = {
        "n_groups": len(groups),
        "n_words": sum(len(g["words"]) for g in groups),
        "backends": {},
    }
    for name in backends:
        out["backends"][name] = backend_index(groups, name, n_perm, seed)
    # phonological null reference (raw SoundClass histogram, no ontology)
    ph_groups = [phonological_features(g["words"]) for g in groups]
    out["phonological_null"] = invariance_index(ph_groups)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--backends", nargs="*", default=None, choices=BACKENDS)
    ap.add_argument("--n-perm", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    r = run(args.data, backends=args.backends, n_perm=args.n_perm, seed=args.seed)

    print("=" * 70)
    print("EXP1 — Synonym invariance per U backend  [no LLM, offline]")
    print("=" * 70)
    print(f"groups={r['n_groups']}  words={r['n_words']}  "
          f"(higher index = more meaning-invariant; ~0 = phonological)\n")
    print(f"{'backend':<16}{'dim':>5}{'within':>9}{'between':>9}{'index':>9}{'p':>9}")
    print("-" * 66)
    for name, b in r["backends"].items():
        print(f"{name:<16}{b['dim']:>5}{b['within']:>9.3f}{b['between']:>9.3f}"
              f"{b['index']:>+9.3f}{b['p_value']:>9.4f}")
    ph = r["phonological_null"]
    print(f"{'(phon. null)':<16}{'-':>5}{ph['within']:>9.3f}{ph['between']:>9.3f}"
          f"{ph['index']:>+9.3f}{'-':>9}")

    print("\n------------------------------ VERDICT -------------------------------")
    best = max(r["backends"].items(), key=lambda kv: kv[1]["index"])
    vm = r["backends"].get("vritti_mapper", {}).get("index", 0.0)
    pm = r["backends"].get("pse_meaning", {}).get("index", 0.0)
    print(f"Most synonym-invariant backend: {best[0]} (index {best[1]['index']:+.3f}, "
          f"p={best[1]['p_value']:.4f}).")
    if "pse_meaning" in r["backends"]:
        delta = pm - vm
        print(f"PSE meaning vs vritti_mapper: index {pm:+.3f} vs {vm:+.3f} "
              f"(Δ={delta:+.3f}).")
    if best[1]["index"] < 0.05 or best[1]["p_value"] > 0.05:
        print("FAIL: even the best backend does NOT cluster synonyms above chance.")
        print("U tracks SOUND, not meaning — including the PSE phoneme→meaning layer.")
        print("Gate-0 (semantic validity) is not cleared. STOP/PIVOT (memo §9).")
    else:
        print("PASS: synonyms cluster above chance for at least one backend — that")
        print("backend carries meaning-aligned structure. Proceed to exp2.")


if __name__ == "__main__":
    main()
