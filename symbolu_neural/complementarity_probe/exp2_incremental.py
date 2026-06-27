"""Experiment 2 — Incremental information: does `E + U` beat `E`?

The core complementarity measurement (SYMBOL_U_RESEARCH_STRATEGY.md §8.2-3). On a
labeled semantic task, train a cross-validated linear probe on:

    E            (Transformer sentence embedding alone)
    E + U        (embedding ++ Symbol-U vector)
    E + null     for every null (shuffled U, random, surface, phonological)

`U` earns complementary value ONLY if `E+U` beats `E` AND beats every `E+null`.
If a random/surface/phonological stream helps as much, the gain was generic
capacity or a confound — not the Symbol-U ontology.

IMPORTANT — backend caveat: a real conclusion requires the `hf` embedding
backend (a genuine semantic encoder). The default `hashing` backend is a
non-semantic, offline stand-in so the harness/smoke test runs without network or
a downloaded model; numbers on it validate the PIPELINE, not the hypothesis.
This is enforced/loud in the output.

Run (smoke, offline):  python -m symbolu_neural.complementarity_probe.exp2_incremental
Run (real):            ... --embeddings hf   (needs HF hub access)
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List

import numpy as np

from .symbolu_engine import SymbolUEngine
from .embeddings import get_embedder
from .nulls import all_nulls, symbolu_matrix
from .metrics import cv_probe_accuracy, concat

DATA = os.path.join(os.path.dirname(__file__), "data", "sentences.jsonl")


def load_labeled(path: str = DATA):
    texts, labels = [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                o = json.loads(line)
                texts.append(o["text"])
                labels.append(o["label"])
    return texts, labels


def run(path: str = DATA, backend: str = "hashing", model_name: str | None = None,
        folds: int = 5, l2: float = 1.0, seed: int = 0) -> dict:
    texts, labels = load_labeled(path)
    classes = sorted(set(labels))
    y = np.array([classes.index(l) for l in labels])

    embedder = get_embedder(backend, model_name)
    E = embedder.encode(texts)
    eng = SymbolUEngine()
    U = symbolu_matrix(texts, eng)
    nulls = all_nulls(texts, U, seed=seed)

    def acc(X):
        return cv_probe_accuracy(X, y, folds=folds, l2=l2, seed=seed)

    base = acc(E)
    results = {
        "backend": backend,
        "is_semantic": embedder.is_semantic,
        "embed_dim": int(E.shape[1]),
        "u_dim": int(U.shape[1]),
        "n": len(texts),
        "classes": classes,
        "E": base,
        "E+U": acc(concat(E, U)),
        "U_alone": acc(U),
    }
    for name, M in nulls.items():
        results[f"E+{name}"] = acc(concat(E, M))
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--embeddings", default="hashing", choices=["hashing", "hf"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    r = run(args.data, backend=args.embeddings, model_name=args.model,
            folds=args.folds, l2=args.l2, seed=args.seed)

    print("=" * 64)
    print("EXP2 — Incremental information: E vs E+U vs E+null")
    print("=" * 64)
    print(f"backend={r['backend']}  semantic={r['is_semantic']}  "
          f"E_dim={r['embed_dim']}  U_dim={r['u_dim']}  n={r['n']}  "
          f"classes={r['classes']}")
    if not r["is_semantic"]:
        print("\n*** WARNING: non-semantic embedding backend. These numbers validate")
        print("*** the PIPELINE ONLY. Re-run with --embeddings hf for a real result.")

    base = r["E"]
    print(f"\n{'features':<16}{'cv_acc':>8}{'Δ vs E':>9}")
    print("-" * 34)
    rows = ["E", "E+U", "E+shuffled_U", "E+random", "E+surface",
            "E+phonological", "U_alone"]
    for k in rows:
        if k in r:
            d = r[k] - base if k != "E" else 0.0
            star = "  <-- claim" if k == "E+U" else ""
            print(f"{k:<16}{r[k]:>8.3f}{d:>+9.3f}{star}")

    print("\n----------------------------- VERDICT ------------------------------")
    eu = r["E+U"]
    null_keys = ["E+shuffled_U", "E+random", "E+surface", "E+phonological"]
    best_null = max(r[k] for k in null_keys if k in r)
    beats_E = eu > base + 1e-6
    beats_nulls = eu > best_null + 1e-6
    if not r["is_semantic"]:
        print("INCONCLUSIVE: non-semantic backend (pipeline smoke only).")
        print(f"E={base:.3f}  E+U={eu:.3f}  best_null={best_null:.3f}.")
        print("Run --embeddings hf on a machine with HF access for a real verdict.")
    elif beats_E and beats_nulls:
        print(f"COMPLEMENTARY (provisional): E+U ({eu:.3f}) > E ({base:.3f}) and >")
        print(f"every null (best {best_null:.3f}). U adds signal beyond E and beyond")
        print("generic/surface/phonological capacity. Proceed up the hierarchy.")
    else:
        print(f"NOT COMPLEMENTARY: E+U ({eu:.3f}) does not beat both E ({base:.3f})")
        print(f"and the best null ({best_null:.3f}). The Symbol-U ontology adds no")
        print("information beyond the embedding / generic capacity. STOP (per memo).")


if __name__ == "__main__":
    main()
