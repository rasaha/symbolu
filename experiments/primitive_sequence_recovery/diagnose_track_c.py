"""Track C EXPLORATORY diagnostics — is the borderline en_gloss effect robust and semantic?

Answers the honest follow-ups to the RunPod run:
  (A) semantic gain: does the static-embedding realizer beat the lexical/LCS baselines?
  (B) multi-seed stability: is the scramble-null p stable, or does it wander across 0.05?
  (C) family-bootstrap CI on MRR_real vs the scramble-null mean (is the delta > 0 robustly?)
  (D) order-scramble sanity: mean-pool is order-insensitive -> should be ~null.

EXPLORATORY ONLY. NOT Track B. Never emits ONTOLOGICAL_SIGNAL. Deterministic, offline. Reads
frozen artifacts; computes no result artifact; touches nothing. Lexical baselines need no
asset (run anywhere); the GloVe realizer needs a hash-pinned vector text file (--glove).

    python3 diagnose_track_c.py                       # lexical baselines only
    python3 diagnose_track_c.py --glove /path/glove.txt [--sha <sha256>] [--boot 2000]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import semantic_realizer as SR                                   # noqa: E402
from baseline_realizer import LexicalOverlapRealizer, OrderSensitiveLexicalRealizer  # noqa: E402

K_CHANCE = sum(1.0 / r for r in range(1, 9)) / 8                 # K=8 random-ranking MRR


def _families(frozen_dir):
    wl = json.loads((frozen_dir / "word_list.json").read_text(encoding="utf-8"))["words"]
    return {w["word_id"]: w["family_id"] for w in wl if not w["exclude_flag"]}


def _per_word_rr(realizer, wa, refs, dz, words):
    rr = {}
    for w in words:
        cand = {c: refs[c] for c in dz[w]}
        order = [cid for cid, _ in SR.rank(realizer, wa[w], cand)]
        rr[w] = 1.0 / (order.index(w) + 1)
    return rr


def _mrr(rr, words):
    return float(np.mean([rr[w] for w in words]))


def diagnose(make_realizer, ac, wa, refs, dz, active, fams, seeds, n_scram, boot):
    """Returns MRR/Top1, multi-seed scramble p, and a family-bootstrap CI on MRR_real."""
    R = make_realizer(ac)
    rr = _per_word_rr(R, wa, refs, dz, active)
    mrr_real = _mrr(rr, active)
    top1 = float(np.mean([1.0 if rr[w] == 1.0 else 0.0 for w in active]))

    # multi-seed scramble null (assignment scramble)
    seed_p, seed_delta = [], []
    for s in seeds:
        rng = np.random.default_rng(s)
        sc = np.array([_mrr(_per_word_rr(make_realizer(SR._scramble_atom_content(ac, rng)),
                                         wa, refs, dz, active), active) for _ in range(n_scram)])
        seed_p.append(float((sc >= mrr_real).mean()))          # one-sided p
        seed_delta.append(mrr_real - float(sc.mean()))

    # family-aware bootstrap CI on MRR_real
    fam_ids = sorted(set(fams[w] for w in active))
    fam_words = {f: [w for w in active if fams[w] == f] for f in fam_ids}
    rng = np.random.default_rng(12345)
    boots = np.empty(boot)
    for b in range(boot):
        pick = rng.choice(len(fam_ids), size=len(fam_ids), replace=True)
        ws = [w for i in pick for w in fam_words[fam_ids[i]]]
        boots[b] = _mrr(rr, ws)
    ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))

    return {"mrr_real": round(mrr_real, 4), "top1": round(top1, 4),
            "seed_p": [round(p, 3) for p in seed_p],
            "seed_delta": [round(d, 4) for d in seed_delta],
            "mrr_ci95": [round(ci[0], 4), round(ci[1], 4)],
            "ci_low_above_chance": ci[0] > K_CHANCE}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glove", default=None, help="path to hash-pinned GloVe text file")
    ap.add_argument("--sha", default=None, help="expected sha256 of --glove")
    ap.add_argument("--n_scram", type=int, default=1000)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    a = ap.parse_args()

    fd = _HERE / "frozen"
    ac, wa, refs, dz, active = SR.load_frozen_corpus(fd, "en_gloss")
    fams = _families(fd)

    realizers = [("lexical_jaccard", lambda x: LexicalOverlapRealizer(x)),
                 ("order_lcs", lambda x: OrderSensitiveLexicalRealizer(x))]
    if a.glove:
        vecs = SR.load_vectors(a.glove, expected_sha256=a.sha)
        realizers.append(("static_embedding_glove", lambda x: SR.StaticEmbeddingRealizer(x, vecs)))

    out = {"track": "C_exploratory_diagnostics", "chance_mrr_k8": round(K_CHANCE, 4),
           "n_words": len(active), "results": {}}
    for name, mk in realizers:
        out["results"][name] = diagnose(mk, ac, wa, refs, dz, active, fams,
                                        a.seeds, a.n_scram, a.boot)

    if "static_embedding_glove" in out["results"]:
        g = out["results"]["static_embedding_glove"]["mrr_real"]
        lex = max(out["results"]["lexical_jaccard"]["mrr_real"],
                  out["results"]["order_lcs"]["mrr_real"])
        out["semantic_gain_over_lexical"] = round(g - lex, 4)

    # honest, non-confirmatory read
    out["note"] = ("EXPLORATORY, English-only. Any positive is capped at REALIZATION_ARTIFACT; "
                   "never ONTOLOGICAL_SIGNAL. Track B remains BLOCKED.")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
