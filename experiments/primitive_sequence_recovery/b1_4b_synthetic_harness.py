#!/usr/bin/env python3
"""B1.4b SYNTHETIC harness — pipeline-mechanics validation ONLY. No real data.

Implements the B1.4b implementation-plan (§11) synthetic harness: it exercises the
L1(synthetic)->L2(F-3 interaction)->L3(probe) mechanics and the terminal-label decision
logic on SYNTHETIC operators and SYNTHETIC targets Y. It touches NO real words, NO real
norms, NO dataset download, and NOTHING in Stage A / symbolu_neural.

The "operators" here are TOY synthetic 4x4 orthogonal matrices built locally from toy
feature vectors. They are labelled synthetic and are deliberately NOT the Stage A
operators (`symbolu_neural/structural_v1`), which are never imported or modified.

Nothing in this file is evidence. A synthetic positive control proves the pipeline CAN
detect interaction signal when one is planted; the phonology/bag/null controls prove it
correctly declines to when one is not.

Run:  python3 b1_4b_synthetic_harness.py            # self-check over fixtures
"""
from __future__ import annotations

import json
import pathlib
from typing import Dict, List, Tuple

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "toy_fixtures" / "b1_4b_synthetic_cases.json"

# ---- terminal labels (must match the pre-registration / implementation plan) ----
LABELS = (
    "L1_L2_L3_ATTRIBUTE_SIGNAL",
    "F_COLLAPSES_TO_PHONOLOGY",
    "BAG_OR_SHUFFLE_EXPLAINS",
    "RANDOM_RELABEL_EXPLAINS",
    "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS",
    "Y_NOT_INDEPENDENT",
    "DECODER_LEAKAGE_INVALID",
    "WORD_LEAKAGE_INVALID",
    "NULL_RETURN_BOTTOM",
    "INCONCLUSIVE",
)

METHODS = ("f3", "phonology", "bag", "shuffle", "random_relabel", "sentiment")

# decision thresholds (synthetic, deterministic; NOT the real study's statistics)
MARGIN = 0.15   # a method must beat another by this CV-correlation margin
CHANCE = 0.20   # scores at/below this are treated as chance (no signal)


# =====================================================================================
# Synthetic L1: TOY operators (NOT Stage A). Orthogonal 4x4 via composed Givens rotations.
# =====================================================================================
def _givens(n: int, i: int, j: int, theta: float) -> np.ndarray:
    g = np.eye(n)
    c, s = np.cos(theta), np.sin(theta)
    g[i, i] = c; g[j, j] = c; g[i, j] = -s; g[j, i] = s
    return g


def toy_operator(feat: np.ndarray) -> np.ndarray:
    """SYNTHETIC toy operator M_u from a 4-dim toy feature vector.

    Orthogonal (norm-preserving, mirroring Stage A's orthogonality) and generally
    non-commuting across units (so commutator/interaction features are non-trivial).
    This is a stand-in, explicitly NOT the frozen Stage A operator.
    """
    f = np.asarray(feat, dtype=float).reshape(4)
    a = 1.3  # angle scale
    m = _givens(4, 0, 1, a * f[0])
    m = _givens(4, 2, 3, a * f[1]) @ m
    m = _givens(4, 1, 2, a * f[2]) @ m
    m = _givens(4, 0, 3, a * f[3]) @ m
    return m


def _synthetic_alphabet(k: int, seed: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """k synthetic units -> (phon features [k,4], operators [k,4,4], sentiment [k])."""
    rng = np.random.default_rng(seed)
    phon = rng.uniform(-1.0, 1.0, size=(k, 4))
    # unit 1 is a PHONOLOGICAL TWIN of unit 0: identical phonology (hence identical
    # operator), distinct identity. This lets a purely identity-based (bag) target be
    # constructed that pooled phonology is STRUCTURALLY blind to, robust under CV.
    phon[1] = phon[0]
    ops = np.stack([toy_operator(phon[u]) for u in range(k)])
    sentiment = rng.uniform(-1.0, 1.0, size=k)
    return phon, ops, sentiment


def _synthetic_words(n: int, k: int, seed: int) -> List[np.ndarray]:
    rng = np.random.default_rng(seed + 1)
    words = []
    for _ in range(n):
        length = int(rng.integers(3, 7))
        words.append(rng.integers(0, k, size=length))
    return words


# =====================================================================================
# Synthetic L2: F-3 operator-interaction features (commutators / non-commutativity).
# NO state-norm / magnitude features (degenerate under orthogonality). The scalars below
# are norms OF the commutator OPERATOR, which is not norm-degenerate.
# =====================================================================================
def f3_features(seq: np.ndarray, ops: np.ndarray) -> np.ndarray:
    ms = [ops[u] for u in seq]
    # adjacent commutator magnitudes
    comm = [np.linalg.norm(ms[i] @ ms[i + 1] - ms[i + 1] @ ms[i], "fro")
            for i in range(len(ms) - 1)]
    comm_mean = float(np.mean(comm)) if comm else 0.0
    comm_max = float(np.max(comm)) if comm else 0.0
    # non-commutativity: ordered product vs reversed product
    prod = np.eye(4)
    for m in ms:
        prod = m @ prod
    rprod = np.eye(4)
    for m in reversed(ms):
        rprod = m @ rprod
    noncommute = float(np.linalg.norm(prod - rprod, "fro"))
    return np.array([comm_mean, comm_max, noncommute], dtype=float)


def phon_features(seq: np.ndarray, phon: np.ndarray) -> np.ndarray:
    # order-insensitive pooled phonological features (place/manner/voicing/sonority proxy)
    return phon[seq].mean(axis=0)


def bag_features(seq: np.ndarray, k: int) -> np.ndarray:
    # order-insensitive unit histogram (counts), normalized
    counts = np.bincount(seq, minlength=k).astype(float)
    return counts / max(1, len(seq))


def sentiment_feature(seq: np.ndarray, sentiment: np.ndarray) -> np.ndarray:
    return np.array([float(sentiment[seq].mean())], dtype=float)


def _shuffled(seq: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + int(seq.sum()) + len(seq))
    s = seq.copy(); rng.shuffle(s); return s


def _relabel_perm(k: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + 99)
    return rng.permutation(k)


def build_feature_matrices(words, phon, ops, sentiment, k, seed) -> Dict[str, np.ndarray]:
    perm = _relabel_perm(k, seed)
    ops_relabel = ops[perm]              # operators reassigned to units (random relabel)
    F = {m: [] for m in METHODS}
    for seq in words:
        F["f3"].append(f3_features(seq, ops))
        F["phonology"].append(phon_features(seq, phon))
        F["bag"].append(bag_features(seq, k))
        F["shuffle"].append(f3_features(_shuffled(seq, seed), ops))
        F["random_relabel"].append(f3_features(seq, ops_relabel))
        F["sentiment"].append(sentiment_feature(seq, sentiment))
    return {m: np.asarray(v, dtype=float) for m, v in F.items()}


# =====================================================================================
# Synthetic L3 probe + metric: k-fold ridge, CV correlation between prediction and Y.
# Capacity-matched: SAME ridge / SAME folds for every method (plan §7).
# =====================================================================================
def _ridge_predict_cv(X: np.ndarray, y: np.ndarray, folds: int = 4, lam: float = 1.0) -> np.ndarray:
    n = len(y)
    fold_id = np.arange(n) % folds
    pred = np.zeros(n)
    for f in range(folds):
        te = fold_id == f
        tr = ~te
        Xtr = X[tr]; ytr = y[tr]
        mu = Xtr.mean(axis=0); sd = Xtr.std(axis=0) + 1e-9
        Xtr_s = (Xtr - mu) / sd
        Xte_s = (X[te] - mu) / sd
        d = Xtr_s.shape[1]
        w = np.linalg.solve(Xtr_s.T @ Xtr_s + lam * np.eye(d), Xtr_s.T @ (ytr - ytr.mean()))
        pred[te] = Xte_s @ w + ytr.mean()
    return pred


def cv_score(X: np.ndarray, y: np.ndarray) -> float:
    """Out-of-sample |Pearson r| between CV prediction and y. ~0 for noise; high for signal."""
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    pred = _ridge_predict_cv(X, y)
    if np.std(pred) < 1e-9 or np.std(y) < 1e-9:
        return 0.0
    r = np.corrcoef(pred, y)[0, 1]
    return float(abs(r)) if np.isfinite(r) else 0.0


def score_all_methods(F: Dict[str, np.ndarray], y: np.ndarray) -> Dict[str, float]:
    return {m: round(cv_score(F[m], y), 4) for m in METHODS}


# =====================================================================================
# Terminal-label decision (pure function). Phonology is PRIMARY; order baselines co-primary.
# =====================================================================================
def decide_label(scores: Dict[str, float], flags: Dict[str, bool] | None = None,
                 margin: float = MARGIN, chance: float = CHANCE) -> str:
    flags = flags or {}
    strong = chance + margin   # a score at/below `strong` is treated as chance-level

    # 1) validity / independence gates first (an invalid run is invalid regardless of scores)
    if flags.get("y_not_independent"):
        return "Y_NOT_INDEPENDENT"
    if flags.get("decoder_gloss_leak"):
        return "DECODER_LEAKAGE_INVALID"
    if flags.get("word_leak"):
        return "WORD_LEAKAGE_INVALID"

    f3 = scores["f3"]
    baselines = {m: scores[m] for m in METHODS if m != "f3"}

    # 2) pure null: nothing (incl. F-3) predicts above chance
    if all(s <= strong for s in scores.values()):
        return "NULL_RETURN_BOTTOM"

    # a CREDIBLE explainer must (a) itself carry signal (>= strong) and (b) tie/beat F-3 (>= f3 - margin)
    explainers = {m: s for m, s in baselines.items() if s >= strong and s >= f3 - margin}

    # 3) F-3 signal: F-3 carries signal, no baseline ties it, and it beats the best baseline by margin
    if f3 >= strong and not explainers and (f3 - max(baselines.values()) > margin):
        return "L1_L2_L3_ATTRIBUTE_SIGNAL"

    # 4) otherwise a baseline explains — phonology is PRIMARY, then order, then relabel, then sentiment
    if "phonology" in explainers:
        return "F_COLLAPSES_TO_PHONOLOGY"
    if "bag" in explainers or "shuffle" in explainers:
        return "BAG_OR_SHUFFLE_EXPLAINS"
    if "random_relabel" in explainers:
        return "RANDOM_RELABEL_EXPLAINS"
    if "sentiment" in explainers:
        return "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS"

    # 5) F-3 leads but not decisively and no baseline credibly explains -> ambiguous
    return "INCONCLUSIVE"


# =====================================================================================
# Synthetic Y generators — each regime plants signal for exactly one method (or none).
# Y is built from the SYNTHETIC feature matrices, so the intended method wins by design.
# =====================================================================================
def make_Y(regime: str, F: Dict[str, np.ndarray], words, phon: np.ndarray, k: int,
           seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed + 7)
    n = len(words)
    noise = rng.normal(0, 1.0, size=n)

    def z(v):  # standardize
        v = np.asarray(v, dtype=float)
        return (v - v.mean()) / (v.std() + 1e-9)

    if regime == "interaction":         # F-3 should win (order/commutator signal)
        return z(F["f3"][:, 2]) * 3.0 + 0.5 * noise
    if regime == "phonology":           # phonology should win (F-3 collapses)
        return z(F["phonology"][:, 0]) * 3.0 + 0.5 * noise
    if regime == "bag":
        # order-insensitive, IDENTITY-based target = count(unit0) - count(unit1), the two
        # phonological twins. Pooled phonology is identical whether a 0 or a 1 appears, so
        # phonology is structurally blind to Y (robust under CV); the unit histogram (bag)
        # separates the twins and predicts it. -> BAG_OR_SHUFFLE.
        c0 = np.array([int((seq == 0).sum()) for seq in words], dtype=float)
        c1 = np.array([int((seq == 1).sum()) for seq in words], dtype=float)
        L = np.array([len(seq) for seq in words], dtype=float)
        yv = (c0 - c1) / L
        return z(yv) * 3.0 + 0.5 * noise
    if regime == "null":                # nothing predicts
        return noise
    raise ValueError(f"unknown pipeline regime: {regime}")


def run_pipeline_case(case: dict) -> dict:
    """Full synthetic pipeline for a 'pipeline' case: build -> features -> Y -> score -> label."""
    seed = int(case.get("seed", 0))
    k = int(case.get("k_units", 5))
    n = int(case.get("n_words", 60))
    phon, ops, sentiment = _synthetic_alphabet(k, seed)
    words = _synthetic_words(n, k, seed)
    F = build_feature_matrices(words, phon, ops, sentiment, k, seed)
    flags = case.get("flags", {})
    if any(flags.get(f) for f in ("y_not_independent", "decoder_gloss_leak", "word_leak")):
        # invalid/independence cases short-circuit before Y is even trusted
        label = decide_label({m: 0.0 for m in METHODS}, flags)
        return {"case": case["name"], "mode": "pipeline", "scores": None,
                "flags": flags, "label": label}
    y = make_Y(case["regime"], F, words, phon, k, seed)
    scores = score_all_methods(F, y)
    label = decide_label(scores, flags)
    return {"case": case["name"], "mode": "pipeline", "scores": scores,
            "flags": flags, "label": label}


def run_scores_case(case: dict) -> dict:
    """Decision-logic case: scores injected directly to exercise a specific label branch."""
    scores = {m: float(case["scores"].get(m, 0.0)) for m in METHODS}
    flags = case.get("flags", {})
    label = decide_label(scores, flags)
    return {"case": case["name"], "mode": "scores", "scores": scores,
            "flags": flags, "label": label}


def run_case(case: dict) -> dict:
    return run_scores_case(case) if case.get("mode") == "scores" else run_pipeline_case(case)


def load_cases() -> List[dict]:
    return json.loads(FIXTURES.read_text())["cases"]


def run_all() -> List[dict]:
    return [run_case(c) for c in load_cases()]


if __name__ == "__main__":
    ok = True
    for res in run_all():
        exp = next(c for c in load_cases() if c["name"] == res["case"]).get("expected_label")
        match = (exp is None) or (res["label"] == exp)
        ok = ok and match
        flag = "OK " if match else "MISMATCH"
        print(f"{flag} {res['case']:<34} -> {res['label']:<38} "
              f"(expected {exp}) scores={res['scores']}")
    print("\nSYNTHETIC ONLY — no real data, no dataset, no Stage A touched.")
    raise SystemExit(0 if ok else 1)
