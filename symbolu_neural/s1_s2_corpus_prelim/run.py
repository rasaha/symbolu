"""Offline corpus-norm preliminary for S1/S2 — EARLY SIGNAL ONLY (confounded).

Tests whether the proposed varṇa attribute table a(·) predicts INDEPENDENT human norms
(Warriner et al. 2013 valence/arousal/dominance; AFINN valence) from phonology alone,
vs. a random-relabel null, a generic acoustic baseline, length, and the raw substrate.

NOT S1/S2: corpus words have lexical meaning, so any result is confounded (the norm IS the
word's meaning; sound→meaning correlation is genuinely small even when real). Treat as an
early indicator, never as proof or falsification. Does NOT touch v3/v4/O1.5 controller code.

Data (not committed; fetched from cited sources):
  Warriner: https://raw.githubusercontent.com/JULIELab/XANEW/master/Ratings_Warriner_et_al.csv
  AFINN:    https://raw.githubusercontent.com/fnielsen/afinn/master/afinn/data/AFINN-en-165.txt
Place both in the path given by --data (default: session scratchpad).
"""
from __future__ import annotations

import csv, math, sys
import numpy as np
from varna_lens.varna_lens import analyze

RNG = np.random.default_rng(20260628)
VOW = set("aeiou")


def load(data_dir):
    norms = {}
    with open(f"{data_dir}/Ratings_Warriner_et_al.csv") as f:
        r = csv.reader(f); h = next(r)
        iW, iV, iA, iD = (h.index(x) for x in ("Word", "V.Mean.Sum", "A.Mean.Sum", "D.Mean.Sum"))
        for row in r:
            w = row[iW].strip().lower()
            if w.isalpha() and 3 <= len(w) <= 12:
                try: norms[w] = (float(row[iV]), float(row[iA]), float(row[iD]))
                except Exception: pass
    afinn = {}
    with open(f"{data_dir}/AFINN-en-165.txt") as f:
        for line in f:
            p = line.split("\t")
            if len(p) == 2 and p[0].isalpha(): afinn[p[0].strip().lower()] = float(p[1])
    return norms, afinn


def vseq(w):
    try: rr, _, _ = analyze(w, model="op")
    except Exception: rr = {}
    seq = [it for it in (rr or {}).get("sequence", []) if it.get("polarity") in ("created", "destroyed")]
    pol = [1 if it["polarity"] == "created" else -1 for it in seq]
    keys = [it.get("key") for it in seq if it.get("key")]
    ev = (rr or {}).get("emergent_valence") or {}
    return pol, keys, float(ev.get("liberating_votes", 0)), float(ev.get("binding_votes", 0))


def pol_feats(pol):
    cre = sum(p > 0 for p in pol); des = sum(p < 0 for p in pol); tot = cre + des
    bal = (cre - des) / tot if tot else 0.0
    flips = sum(pol[i] != pol[i + 1] for i in range(len(pol) - 1))
    tens = flips / (len(pol) - 1) if len(pol) > 1 else 0.0
    p = cre / tot if tot else .5
    ent = 0 if p in (0, 1) else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    return [bal, tens, 1 - ent]


def acoustic(w):
    vc = sum(c in VOW for c in w); L = len(w)
    return [vc / L, L, len(set(w)), vc, L - vc]


def cv_r2(X, y, k=5):
    X = np.asarray(X, float); y = np.asarray(y, float)
    m = ~np.isnan(y); X, y = X[m], y[m]
    X = (X - X.mean(0)) / np.where(X.std(0) < 1e-9, 1, X.std(0))
    X = np.c_[np.ones(len(X)), X]; idx = np.arange(len(X)); RNG.shuffle(idx)
    fold = np.array_split(idx, k); pred = np.zeros(len(X))
    for i in range(k):
        te = fold[i]; tr = np.concatenate([fold[j] for j in range(k) if j != i])
        beta, _, _, _ = np.linalg.lstsq(X[tr], y[tr], rcond=None); pred[te] = X[te] @ beta
    return 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)


def main(data_dir, n=2500, k_relabel=200):
    norms, afinn = load(data_dir)
    words = sorted(norms); RNG.shuffle(words); words = words[:n]
    keyset = set(); rows = []
    for w in words:
        pol, keys, lib, bind = vseq(w); keyset.update(keys)
        vr = lib / (lib + bind) if (lib + bind) else .5
        rows.append(dict(keys=keys, a_full=[vr] + pol_feats(pol), a_pol=pol_feats(pol),
                         ac=acoustic(w), V=norms[w][0], A=norms[w][1], D=norms[w][2],
                         AF=afinn.get(w, np.nan)))
    keys = sorted(keyset)
    out = {"n": len(rows), "keys": len(keys), "per_norm": {}}
    for norm in ["V", "A", "D", "AF"]:
        y = [r[norm] for r in rows]
        res = {"a_full": cv_r2([r["a_full"] for r in rows], y),
               "a_pol": cv_r2([r["a_pol"] for r in rows], y),
               "acoustic": cv_r2([r["ac"] for r in rows], y),
               "length": cv_r2([[r["ac"][1]] for r in rows], y),
               "acoustic_plus_a": cv_r2([r["ac"] + r["a_pol"] for r in rows], y)}
        null = []
        for _ in range(k_relabel):
            smap = {kk: int(v) for kk, v in zip(keys, RNG.integers(0, 2, len(keys)) * 2 - 1)}
            null.append(cv_r2([pol_feats([smap.get(kk, 1) for kk in r["keys"]]) for r in rows], y))
        null = np.array(null)
        res["relabel_null_mean"] = float(null.mean())
        res["relabel_null_p95"] = float(np.percentile(null, 95))
        res["real_percentile"] = float((null < res["a_pol"]).mean())
        res["incremental_over_acoustic"] = res["acoustic_plus_a"] - res["acoustic"]
        out["per_norm"][norm] = {k2: round(v, 4) for k2, v in res.items()}
    return out


if __name__ == "__main__":
    import json
    dd = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(main(dd), indent=2))
