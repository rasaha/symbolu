"""Generate a SYNTHETIC toy grounding dataset.

WARNING — SYNTHETIC. Labels are a deterministic function of SURFACE features
(vowel count, word length), not real Vritti/Guna/Kosha semantics. Train and val
use DISJOINT vocabularies, so a head that learns the surface rule generalizes to
unseen words (a PASS validates the *harness and a learnable signal*), while a head
that only memorizes word identity scores at chance on val (caught as a kill
criterion). This is a pipeline test, NOT validation of the Vritti hypothesis.

Rule (documented in meta.json):
    vritti = min(vowel_count, 4)
    aspect = min(len - 1, 9)
    guna   = min(vowel_count, 2)
    kosha  = min((len - 1) // 2, 4)

Run:
    python -m symbolu_neural.stage1.make_toy_grounding_dataset --out-dir data/toy_grounding
"""
from __future__ import annotations

import argparse
import json
import os
import random
from typing import Dict, List

from .labels import VRITTI, ASPECT, GUNA, KOSHA

_C = "bcdfghklmnprstv"
_V = "aeiou"


def _vowels(w: str) -> int:
    return sum(c in _V for c in w)


def _label_names(w: str) -> Dict[str, str]:
    vc, n = _vowels(w), len(w)
    return {
        "vritti": VRITTI[min(vc, 4)],
        "aspect": ASPECT[min(n - 1, 9)],
        "guna": GUNA[min(vc, 2)],
        "kosha": KOSHA[min((n - 1) // 2, 4)],
    }


def _gen_word(rng: random.Random) -> str:
    syl = rng.randint(1, 3)
    w = ""
    for _ in range(syl):
        w += rng.choice(_C) + rng.choice(_V)
        if rng.random() < 0.4:
            w += rng.choice(_C)
    return w


def _unique_words(rng: random.Random, n: int) -> List[str]:
    seen = set()
    while len(seen) < n:
        seen.add(_gen_word(rng))
    return list(seen)


def _rows(words: List[str], rng: random.Random, n_rows: int,
          heads: List[str]) -> List[dict]:
    rows = []
    for _ in range(n_rows):
        k = rng.randint(4, 10)
        units = [rng.choice(words) for _ in range(k)]
        row = {"text": " ".join(units), "units": units}
        for h in heads:
            row[h] = [_label_names(u)[h] for u in units]
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data/toy_grounding")
    ap.add_argument("--n-train", type=int, default=400)
    ap.add_argument("--n-val", type=int, default=120)
    ap.add_argument("--vocab", type=int, default=300, help="unique words (split disjoint)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--heads", default="vritti,aspect,guna,kosha")
    args = ap.parse_args()

    heads = [h.strip() for h in args.heads.split(",") if h.strip()]
    rng = random.Random(args.seed)
    words = _unique_words(rng, args.vocab)
    rng.shuffle(words)
    cut = len(words) // 2
    train_vocab, val_vocab = words[:cut], words[cut:]   # DISJOINT
    assert not (set(train_vocab) & set(val_vocab))

    os.makedirs(args.out_dir, exist_ok=True)
    train = _rows(train_vocab, rng, args.n_train, heads)
    val = _rows(val_vocab, rng, args.n_val, heads)
    for name, rows in [("train.jsonl", train), ("val.jsonl", val)]:
        with open(os.path.join(args.out_dir, name), "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    meta = {
        "synthetic": True,
        "warning": "SYNTHETIC surface-feature labels; NOT real Vritti semantics. "
                   "A PASS validates the harness/plumbing and a learnable signal, "
                   "not the Vritti hypothesis.",
        "rule": {"vritti": "min(vowel_count,4)", "aspect": "min(len-1,9)",
                 "guna": "min(vowel_count,2)", "kosha": "min((len-1)//2,4)"},
        "train_val_vocab_disjoint": True,
        "heads": heads, "seed": args.seed,
    }
    with open(os.path.join(args.out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"wrote {len(train)} train / {len(val)} val rows to {args.out_dir} "
          f"(SYNTHETIC; disjoint vocab; heads={heads})")


if __name__ == "__main__":
    main()
