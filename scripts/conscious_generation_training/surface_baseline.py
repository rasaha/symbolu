"""surface_baseline.py — anti-circularity GUARDRAIL for the Guna/Vritti probe (torch-free, numpy, CPU).
Pre-reg: docs/CG_GUNA_VRITTI_LABEL_SOURCE_PREREG.md §7.

Computes how predictable each label already is from TRANSPARENT SURFACE FEATURES of prompt+response text
(length, hedging, refusal, imperatives, comparison/speculation markers, …). A hidden-state probe must
BEAT this baseline by a margin to claim anything non-trivial; a label predicted by surface features at
AUROC ≥ 0.85 is flagged SURFACE_CONFOUNDED. This makes NO signal claim and trains nothing — it only caps
what a future real-label probe is allowed to conclude.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

import numpy as np

try:
    from .guna_vritti_metrics import auroc
    from .guna_vritti_heads import GUNA_NAMES, VRITTI_NAMES
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from conscious_generation_training.guna_vritti_metrics import auroc          # type: ignore
    from conscious_generation_training.guna_vritti_heads import GUNA_NAMES, VRITTI_NAMES  # type: ignore

SURFACE_CONFOUNDED_THRESHOLD = 0.85
PROBE_MARGIN = 0.05

_HEDGE = ("maybe", "perhaps", "might", "possibly", "i think", "not sure", "unclear", "it depends",
          "i guess", "probably", "seems")
_REFUSAL = ("i don't know", "i do not know", "cannot", "can't help", "i'm not able", "i am not able",
            "as an ai", "no idea", "unable to", "i won't")
_IMPERATIVE = ("first,", "first ", "then ", "next,", "step ", "do ", "use ", "run ", "click ", "open ",
               "start by", "follow ", "begin by")
_COMPARISON = ("however", "compare", "tradeoff", "trade-off", " vs ", "versus", "whereas",
               "on the other hand", "pros", "cons", "alternatively")
_SPECULATION = ("imagine", "suppose", "hypothetically", "what if", "could be", "might be", "fiction",
                "pretend", "let's say")
_LIST_RE = re.compile(r"(^|\n)\s*(\d+[.)]|[-*•])\s", re.M)
_SENT_RE = re.compile(r"[.!?]+")

SURFACE_FEATURE_NAMES = ["word_count", "char_count", "sentence_count", "avg_word_len", "question_marks",
                         "numeral_density", "list_markers", "hedge_density", "refusal_density",
                         "imperative_density", "comparison_density", "speculation_density"]


def _density(text: str, needles) -> float:
    t = " " + text.lower() + " "
    return sum(t.count(n) for n in needles)


def surface_features(prompt: str, response: str) -> Dict[str, float]:
    """Transparent, deterministic surface features of the RESPONSE (prompt kept for context only)."""
    r = response or ""
    words = r.split()
    wc = max(1, len(words))
    sents = max(1, len([s for s in _SENT_RE.split(r) if s.strip()]))
    return {
        "word_count": float(len(words)),
        "char_count": float(len(r)),
        "sentence_count": float(sents),
        "avg_word_len": float(np.mean([len(w) for w in words])) if words else 0.0,
        "question_marks": float(r.count("?")),
        "numeral_density": float(sum(c.isdigit() for c in r)) / max(1, len(r)),
        "list_markers": float(len(_LIST_RE.findall(r))),
        "hedge_density": _density(r, _HEDGE) / wc,
        "refusal_density": _density(r, _REFUSAL) / wc,
        "imperative_density": _density(r, _IMPERATIVE) / wc,
        "comparison_density": _density(r, _COMPARISON) / wc,
        "speculation_density": _density(r, _SPECULATION) / wc,
    }


def feature_matrix(rows: List[dict]) -> np.ndarray:
    return np.array([[surface_features(r.get("prompt", ""), r.get("response", ""))[f]
                      for f in SURFACE_FEATURE_NAMES] for r in rows], float)


def best_single_feature_auroc(X: np.ndarray, y: np.ndarray):
    """Max directional single-feature AUROC for binary y. Returns (auroc, feature_name). Conservative
    (no fitting → no overfit); a multivariate fit would be ≥ this."""
    y = np.asarray(y, int)
    if len(set(y.tolist())) < 2:
        return None, None
    best, best_f = 0.5, None
    for j, name in enumerate(SURFACE_FEATURE_NAMES):
        a = auroc(X[:, j], y)
        if a is None:
            continue
        a = max(a, 1.0 - a)                               # directional
        if a > best:
            best, best_f = a, name
    return round(best, 4), best_f


def _logistic_oof_auroc(X: np.ndarray, y: np.ndarray, k: int = 5, seed: int = 0, iters: int = 400):
    """Combined-feature surface AUROC via numpy logistic regression, k-fold OOF. None if N too small or a
    fold is single-class (avoids overfit nonsense on tiny N)."""
    y = np.asarray(y, int)
    n = len(y)
    if n < 2 * k or len(set(y.tolist())) < 2:
        return None
    mu, sd = X.mean(0), X.std(0) + 1e-8
    Xs = (X - mu) / sd
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, k)
    oof = np.full(n, np.nan)
    for f in range(k):
        te = folds[f]; tr = np.concatenate([folds[j] for j in range(k) if j != f])
        if len(set(y[tr].tolist())) < 2:
            return None
        w = np.zeros(Xs.shape[1]); b = 0.0
        for _ in range(iters):
            z = Xs[tr] @ w + b
            p = 1.0 / (1.0 + np.exp(-z))
            g = p - y[tr]
            w -= 0.1 * (Xs[tr].T @ g / len(tr) + 1e-3 * w)
            b -= 0.1 * float(g.mean())
        oof[te] = 1.0 / (1.0 + np.exp(-(Xs[te] @ w + b)))
    return auroc(oof, y)


def _label_surface_auroc(X, y) -> dict:
    single, feat = best_single_feature_auroc(X, y)
    logit = _logistic_oof_auroc(X, y)
    surface = max([v for v in (single, logit) if v is not None], default=None)
    return {"surface_auroc": surface, "best_single_feature": feat,
            "single_feature_auroc": single, "logistic_oof_auroc": logit,
            "confounded": bool(surface is not None and surface >= SURFACE_CONFOUNDED_THRESHOLD)}


def surface_baseline(rows: List[dict]) -> dict:
    """Per-label surface predictability. Guna: per labelled dim (skip null-masked); Vritti: one-vs-rest."""
    X = feature_matrix(rows)
    guna_y = np.array([[(-1 if v is None else int(v)) for v in r.get("labels", {}).get("guna", [None] * 6)]
                       for r in rows], int)
    vmap = {n.lower(): i for i, n in enumerate(VRITTI_NAMES)}
    vy = np.array([vmap.get(str(r.get("labels", {}).get("vritti", "")).lower(), -1) for r in rows], int)

    guna = {}
    for j, name in enumerate(GUNA_NAMES):
        col = guna_y[:, j]
        mask = col >= 0                                   # skip null/masked dims
        guna[name] = ({"masked": True} if mask.sum() == 0
                      else _label_surface_auroc(X[mask], col[mask]))
    vritti = {}
    for c, name in enumerate(VRITTI_NAMES):
        yc = (vy == c).astype(int)
        vritti[name] = ({"absent": True} if yc.sum() == 0 or (vy >= 0).sum() == 0
                        else _label_surface_auroc(X[vy >= 0], yc[vy >= 0]))
    confounded = ([f"guna:{n}" for n, d in guna.items() if d.get("confounded")]
                  + [f"vritti:{n}" for n, d in vritti.items() if d.get("confounded")])
    return {"n": len(rows), "threshold": SURFACE_CONFOUNDED_THRESHOLD,
            "surface_features": SURFACE_FEATURE_NAMES, "guna": guna, "vritti": vritti,
            "surface_confounded_labels": confounded,
            "note": "GUARDRAIL only: a hidden-state probe must BEAT these surface AUROCs by "
                    f"≥{PROBE_MARGIN} to claim non-trivial signal. No signal claim is made here."}


def probe_beats_surface(probe_auroc: Optional[float], surface_auroc: Optional[float],
                        margin: float = PROBE_MARGIN) -> Optional[bool]:
    """Future-use helper: did the probe beat the surface baseline by `margin`? None if either is missing."""
    if probe_auroc is None or surface_auroc is None:
        return None
    return bool(probe_auroc >= surface_auroc + margin)
