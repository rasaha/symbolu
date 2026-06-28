"""O1.5 construct-validity engine — offline only. No LLM, no policy, no v3/v4 imports.

Reading features (the Symbol-U SEMANTIC reading, aggregated per text):
  valence_ratio   : liberating_votes / (lib+bind)            [emergent valence]
  polarity_balance: (#created - #destroyed) / (#created+#destroyed)
  tension         : fraction of adjacent created/destroyed polarity FLIPS
  coherence       : 1 - binary entropy of created/destroyed proportion
  mean_sign       : mean whole-word essence sign (+1/-1/0)

Phonetic substrate (the content-blind signal v3/v4 used): the 5-d vritti distribution.
Shuffle control: a fixed random varṇa-key -> polarity permutation, applied consistently,
recomputing the polarity-derived features (tests whether the SPECIFIC pole assignment works).
"""
from __future__ import annotations

import math
import numpy as np

from varna_lens.varna_lens import analyze
from symbolu_core.formulas.acoustic_unit_mapper import map_acoustic_units
from symbolu_core.formulas.vritti_mapper import (
    assign_vritti, get_vritti_distribution, VrittiType)

READING_FEATS = ["valence_ratio", "polarity_balance", "tension", "coherence", "mean_sign"]
SUBSTRATE_FEATS = [v.name for v in VrittiType]
_RNG = np.random.default_rng(20260628)

# ---- per-word varṇa extraction (cached) -----------------------------------------
_cache: dict = {}


def _word_read(word: str):
    if word in _cache:
        return _cache[word]
    try:
        r, _, _ = analyze(word, model="op")
    except Exception:
        r = {}
    r = r or {}
    seq = [it for it in r.get("sequence", []) if it.get("polarity") in ("created", "destroyed")]
    pol = [1 if it["polarity"] == "created" else -1 for it in seq]
    keys = [it.get("key") for it in seq]
    ev = r.get("emergent_valence") or {}
    sign = {"+": 1.0, "-": -1.0, "−": -1.0}.get(str((r.get("whole_word_essence") or {}).get("sign", "")), 0.0)
    out = {"pol": pol, "keys": keys,
           "lib": float(ev.get("liberating_votes", 0)), "bind": float(ev.get("binding_votes", 0)),
           "sign": sign}
    _cache[word] = out
    return out


def _words(text: str):
    return [w.strip(".,!?;:").lower() for w in text.split() if w.strip(".,!?;:")]


def _feats_from_pol(pol, lib, bind, signs):
    cre = sum(1 for p in pol if p > 0)
    des = sum(1 for p in pol if p < 0)
    tot = cre + des
    polarity_balance = (cre - des) / tot if tot else 0.0
    flips = sum(1 for i in range(len(pol) - 1) if pol[i] != pol[i + 1])
    tension = flips / (len(pol) - 1) if len(pol) > 1 else 0.0
    p = cre / tot if tot else 0.5
    ent = 0.0 if p in (0.0, 1.0) else -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    coherence = 1.0 - ent
    valence_ratio = lib / (lib + bind) if (lib + bind) else 0.5
    mean_sign = float(np.mean(signs)) if signs else 0.0
    return [valence_ratio, polarity_balance, tension, coherence, mean_sign]


def reading_vector(text: str):
    pol, lib, bind, signs = [], 0.0, 0.0, []
    for w in _words(text):
        d = _word_read(w)
        pol += d["pol"]; lib += d["lib"]; bind += d["bind"]; signs.append(d["sign"])
    return np.array(_feats_from_pol(pol, lib, bind, signs), float)


def substrate_vector(text: str):
    units = map_acoustic_units(text)
    vs = [assign_vritti(u) for u in units]
    d = get_vritti_distribution(vs) if vs else {v: 0.0 for v in VrittiType}
    return np.array([float(d[v]) for v in VrittiType], float)


# ---- shuffle control: fixed varṇa-key -> polarity permutation --------------------
def _build_shuffle_map(texts):
    keys = set()
    for t in texts:
        for w in _words(t):
            keys.update(k for k in _word_read(w)["keys"] if k)
    keys = sorted(keys)
    vals = _RNG.integers(0, 2, len(keys)) * 2 - 1   # +1/-1 random, consistent
    return {k: int(v) for k, v in zip(keys, vals)}


def reading_vector_shuffled(text: str, smap: dict):
    pol, lib, bind, signs = [], 0.0, 0.0, []
    for w in _words(text):
        d = _word_read(w)
        pol += [smap.get(k, 1) for k in d["keys"] if k]   # shuffled poles
        lib += d["lib"]; bind += d["bind"]; signs.append(d["sign"])
    return np.array(_feats_from_pol(pol, lib, bind, signs), float)


# ---- baselines -------------------------------------------------------------------
def sentiment_vector(text: str):
    from .data import POS_WORDS, NEG_WORDS
    ws = _words(text)
    pos = sum(1 for w in ws if w in POS_WORDS)
    neg = sum(1 for w in ws if w in NEG_WORDS)
    n = len(ws) or 1
    return np.array([(pos - neg) / n, pos / n, neg / n], float)


def length_vector(text: str):
    return np.array([len(_words(text))], float)


# ---- distance helpers ------------------------------------------------------------
def zscore(M):
    M = np.asarray(M, float)
    mu, sd = M.mean(0), M.std(0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    return (M - mu) / sd


def class_separation(vectors, labels):
    """inter/intra ratio on z-scored vectors. >1 => classes separate."""
    Z = zscore(vectors)
    labs = np.array(labels)
    intra, inter = [], []
    for i in range(len(Z)):
        for j in range(i + 1, len(Z)):
            d = float(np.linalg.norm(Z[i] - Z[j]))
            (intra if labs[i] == labs[j] else inter).append(d)
    mi = np.mean(intra) if intra else 0.0
    me = np.mean(inter) if inter else 0.0
    return (me / mi if mi else float("nan")), mi, me
