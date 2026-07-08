#!/usr/bin/env python3
"""B1.4b′ evidence-run scorer / harness. SYNTHETIC-TESTABLE; does NOT run the real McRae test.

Implements the machinery specified in `B1_4B_PRIME_MCRAE_FREEZE_PACKAGE_PLAN.md` /
`B1_4B_PRIME_LAYER3_DECODER_Y_DESIGN.md`:
  - F-3 extractor over Stage A′ phoneme/operator sequences (L2),
  - all required baselines (phonology, phonological-similarity, bag-of-phonemes, shuffled-order,
    random/relabel operators, length/frequency, sentiment/lexicon, chance/null) with explicit
    BASELINE_PENDING_SOURCE stubs where a source is not supplied,
  - a matched-capacity regularized-linear decoder + concept-level CV,
  - metric + terminal-label logic (delta-vs-phonology primary, delta-vs-order co-primary).

HARD RULE: this module NEVER runs the real evidence test on real McRae Y. `score()` is generic;
the committed tests and `__main__` use SYNTHETIC Y only. Real evidence scoring requires a
separate, explicit operator-authorized freeze + run (not performed here). Stage A′ is imported
READ-ONLY; frozen Stage A is untouched. No raw McRae data / private Y is read or committed here.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stage_a_prime_coverage as A   # READ-ONLY (PHONEMES, phoneme_operator, operator_sequence, normalize)

LABELS = (
    "L1_L2_L3_ATTRIBUTE_SIGNAL",
    "F_COLLAPSES_TO_PHONOLOGY",
    "BAG_OR_SHUFFLE_EXPLAINS",
    "RANDOM_RELABEL_EXPLAINS",
    "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS",
    "Y_NOT_INDEPENDENT",
    "DECODER_LEAKAGE_INVALID",
    "NULL_RETURN_BOTTOM",
    "INCONCLUSIVE",
)
BASELINE_PENDING_SOURCE = "BASELINE_PENDING_SOURCE"

MARGIN = 0.15
CHANCE = 0.20
LAM = 1.0            # frozen ridge hyperparameter (single-value grid; matched across all methods)
FOLDS = 4
CV_SEED = 0

INVENTORY = list(A.PHONEMES.keys())
_PH_INDEX = {p: i for i, p in enumerate(INVENTORY)}


# =====================================================================================
# operator helpers (Stage A′, read-only)
# =====================================================================================
def _ops(phonemes):
    return [A.phoneme_operator(p) for p in phonemes]


def _f3_from_ops(ops):
    comm = [np.linalg.norm(ops[i] @ ops[i + 1] - ops[i + 1] @ ops[i], "fro") for i in range(len(ops) - 1)]
    prod = np.eye(4)
    for m in ops:
        prod = m @ prod
    rprod = np.eye(4)
    for m in reversed(ops):
        rprod = m @ rprod
    nonc = float(np.linalg.norm(prod - rprod, "fro"))
    return [float(np.mean(comm)) if comm else 0.0, float(np.max(comm)) if comm else 0.0, nonc]


# =====================================================================================
# L2 F-3 extractor + baseline extractors. Each returns [n, d]; finite-checked.
# NOTE: F-3 magnitude summaries are INVARIANT to full sequence reversal
#       (‖[a,b]‖=‖[b,a]‖, ‖prod−rprod‖ symmetric) — a recorded limitation.
# =====================================================================================
def extract_f3(records):
    return _finite(np.array([_f3_from_ops(_ops(r["phonemes"])) for r in records], float))


def extract_phonology(records):        # plain pooled articulatory features (4-dim)
    out = []
    for r in records:
        v = np.array([A.PHONEMES[p] for p in r["phonemes"]], float)
        out.append(v.mean(axis=0) if len(v) else np.zeros(A.K))
    return _finite(np.array(out, float))


def extract_phon_similarity(records):  # richer sound representation: mean+std+first+last vecs (16-dim)
    out = []
    for r in records:
        v = np.array([A.PHONEMES[p] for p in r["phonemes"]], float)
        if len(v) == 0:
            out.append(np.zeros(4 * A.K)); continue
        out.append(np.concatenate([v.mean(0), v.std(0), v[0], v[-1]]))
    return _finite(np.array(out, float))


def extract_bag(records):              # order-destroyed phoneme identity histogram
    out = np.zeros((len(records), len(INVENTORY)))
    for i, r in enumerate(records):
        for p in r["phonemes"]:
            out[i, _PH_INDEX[p]] += 1.0
        if r["phonemes"]:
            out[i] /= len(r["phonemes"])
    return _finite(out)


def extract_shuffled(records, seed=17):
    out = []
    for r in records:
        rng = np.random.default_rng(seed + len(r["phonemes"]) + sum(_PH_INDEX[p] for p in r["phonemes"]))
        seq = list(r["phonemes"]); rng.shuffle(seq)
        out.append(_f3_from_ops(_ops(seq)) if len(seq) >= 2 else [0.0, 0.0, 0.0])
    return _finite(np.array(out, float))


def extract_random_relabel(records, seed=23):
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(INVENTORY))
    relabel = {INVENTORY[i]: INVENTORY[perm[i]] for i in range(len(INVENTORY))}
    out = []
    for r in records:
        ops = [A.phoneme_operator(relabel[p]) for p in r["phonemes"]]
        out.append(_f3_from_ops(ops) if len(ops) >= 2 else [0.0, 0.0, 0.0])
    return _finite(np.array(out, float))


def extract_length_frequency(records):
    # length is always available; frequency requires an external covariate.
    have_freq = all("freq" in r.get("covars", {}) for r in records)
    cols = [[len(r["phonemes"])] for r in records]
    if have_freq:
        for i, r in enumerate(records):
            cols[i].append(float(r["covars"]["freq"]))
        return _finite(np.array(cols, float)), None
    return _finite(np.array(cols, float)), BASELINE_PENDING_SOURCE   # length-only; freq pending


def extract_sentiment(records):
    have = all("sentiment" in r.get("covars", {}) for r in records)
    if not have:
        return None, BASELINE_PENDING_SOURCE
    return _finite(np.array([[float(r["covars"]["sentiment"])] for r in records], float)), None


def extract_chance(records):           # constant -> predicts the training marginal (~chance)
    return np.zeros((len(records), 1))


def _finite(X):
    if not np.all(np.isfinite(X)):
        raise ValueError("non-finite features")
    return X


# =====================================================================================
# decoder/probe + concept-level CV. Matched capacity: SAME ridge LAM, SAME folds for all methods.
# =====================================================================================
def _folds(n, folds=FOLDS, seed=CV_SEED):
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    f = np.empty(n, int)
    for i, idx in enumerate(perm):
        f[idx] = i % folds          # concept-level: each row (concept) in exactly one test fold
    return f


def _ridge_cv_pred(X, Y, folds=FOLDS, seed=CV_SEED, lam=LAM):
    n = len(Y)
    fid = _folds(n, folds, seed)
    P = np.zeros_like(Y, dtype=float)
    for f in range(folds):
        te = fid == f; tr = ~te
        Xtr = X[tr]; Ytr = Y[tr]
        mu = Xtr.mean(0); sd = Xtr.std(0) + 1e-9
        Xtr_s = (Xtr - mu) / sd; Xte_s = (X[te] - mu) / sd
        ymu = Ytr.mean(0)
        d = Xtr_s.shape[1]
        W = np.linalg.solve(Xtr_s.T @ Xtr_s + lam * np.eye(d), Xtr_s.T @ (Ytr - ymu))
        P[te] = Xte_s @ W + ymu
    return P


def cv_score(X, Y):
    """Out-of-sample mean |Pearson r| across Y columns (concept-level CV). ~0 for noise."""
    X = X.reshape(-1, 1) if X.ndim == 1 else X
    Y = Y.reshape(-1, 1) if Y.ndim == 1 else Y
    P = _ridge_cv_pred(X, Y)
    cs = []
    for j in range(Y.shape[1]):
        if np.std(P[:, j]) < 1e-9 or np.std(Y[:, j]) < 1e-9:
            continue
        r = np.corrcoef(P[:, j], Y[:, j])[0, 1]
        if np.isfinite(r):
            cs.append(abs(r))
    return float(np.mean(cs)) if cs else 0.0


# =====================================================================================
# metrics: Holm correction + a permutation-null hook (real p-values only when a run supplies them)
# =====================================================================================
def holm_correct(pvalues):
    idx = sorted(range(len(pvalues)), key=lambda i: pvalues[i])
    m = len(pvalues); out = [0.0] * m; running = 0.0
    for rank, i in enumerate(idx):
        adj = min(1.0, (m - rank) * pvalues[i]); running = max(running, adj); out[i] = running
    return out


def permutation_pvalue_hook(observed_delta, permute_fn=None, n=1000, seed=CV_SEED):
    """Placeholder hook: with a real permute_fn (label-permutation), returns an empirical p.
    Without one (pre-run), returns None (not fabricated)."""
    if permute_fn is None:
        return None
    rng = np.random.default_rng(seed)
    ge = sum(1 for _ in range(n) if permute_fn(rng) >= observed_delta)
    return (ge + 1) / (n + 1)


# =====================================================================================
# scoring + terminal label
# =====================================================================================
def score_all(records, Y, seed=CV_SEED):
    Y = np.asarray(Y, float)
    scores = {}
    pending = {}
    scores["f3"] = cv_score(extract_f3(records), Y)
    scores["phonology"] = cv_score(extract_phonology(records), Y)
    scores["phon_similarity"] = cv_score(extract_phon_similarity(records), Y)
    scores["bag"] = cv_score(extract_bag(records), Y)
    scores["shuffled"] = cv_score(extract_shuffled(records), Y)
    scores["random_relabel"] = cv_score(extract_random_relabel(records), Y)
    lf, lf_pending = extract_length_frequency(records)
    scores["length_frequency"] = cv_score(lf, Y)
    if lf_pending:
        pending["length_frequency"] = BASELINE_PENDING_SOURCE   # frequency component pending
    sent, sent_pending = extract_sentiment(records)
    if sent is None:
        pending["sentiment"] = BASELINE_PENDING_SOURCE
    else:
        scores["sentiment"] = cv_score(sent, Y)
    scores["chance"] = cv_score(extract_chance(records), Y)
    return round_scores(scores), pending


def round_scores(scores):
    return {k: round(v, 4) for k, v in scores.items()}


def decide_label(scores, flags=None, margin=MARGIN, chance=CHANCE):
    flags = flags or {}
    strong = chance + margin
    if flags.get("y_not_independent"):
        return "Y_NOT_INDEPENDENT"
    if flags.get("decoder_leak"):
        return "DECODER_LEAKAGE_INVALID"
    if "f3" not in scores:
        return "INCONCLUSIVE"
    f3 = scores["f3"]
    baselines = {k: v for k, v in scores.items() if k != "f3"}
    if not baselines or all(s <= strong for s in scores.values()):
        return "NULL_RETURN_BOTTOM"
    explainers = {k: v for k, v in baselines.items() if v >= strong and v >= f3 - margin}
    if f3 >= strong and not explainers and (f3 - max(baselines.values()) > margin):
        return "L1_L2_L3_ATTRIBUTE_SIGNAL"
    if explainers.keys() & {"phonology", "phon_similarity"}:
        return "F_COLLAPSES_TO_PHONOLOGY"
    if explainers.keys() & {"bag", "shuffled"}:
        return "BAG_OR_SHUFFLE_EXPLAINS"
    if "random_relabel" in explainers:
        return "RANDOM_RELABEL_EXPLAINS"
    if "sentiment" in explainers:
        return "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS"
    return "INCONCLUSIVE"


def score(records, Y, flags=None):
    """Generic scorer. SYNTHETIC/interface use only — NOT for the real evidence run here."""
    scores, pending = score_all(records, Y)
    label = decide_label(scores, flags)
    return {"scores": scores, "pending_baselines": pending, "label": label,
            "primary_endpoint": "delta_vs_phonology", "co_primary": "delta_vs_bag_shuffle_random"}


# =====================================================================================
# B1.4b′ ARM STRUCTURE.  These are PREDICTOR-FEATURE arms (each produces a feature matrix
# for the SAME retained concepts; the SAME matched-capacity decoder predicts the SAME
# McRae Y). They are NOT B1.3-style LLM prompt/rendering/judge arms — no text is generated
# and no judge preference is elicited.
# =====================================================================================
ARMS = [
    {"id": "A_F3_REAL",            "key": "f3",               "role": "candidate_structural_interaction"},
    {"id": "B_PHONOLOGY_PLAIN",    "key": "phonology",        "role": "primary_baseline_phonology"},
    {"id": "C_PHONOLOGY_SIMILARITY","key": "phon_similarity", "role": "baseline_phonology_similarity"},
    {"id": "D_BAG_OF_PHONEMES",    "key": "bag",              "role": "co_primary_order_ablation"},
    {"id": "E_SHUFFLED_ORDER_F3",  "key": "shuffled",         "role": "co_primary_order_ablation"},
    {"id": "F_RANDOM_RELABEL_F3",  "key": "random_relabel",   "role": "co_primary_operator_identity"},
    {"id": "G_LENGTH_FREQUENCY",   "key": "length_frequency", "role": "baseline_length_frequency"},
    {"id": "H_SENTIMENT_LEXICON",  "key": "sentiment",        "role": "baseline_sentiment"},
    {"id": "I_NULL_CHANCE",        "key": "chance",           "role": "null_chance"},
]
ARM_TO_KEY = {a["id"]: a["key"] for a in ARMS}
KEY_TO_ARM = {a["key"]: a["id"] for a in ARMS}
CANDIDATE_ARM = "A_F3_REAL"
PHONOLOGY_ARMS = ("B_PHONOLOGY_PLAIN", "C_PHONOLOGY_SIMILARITY")
ORDER_ARMS = ("D_BAG_OF_PHONEMES", "E_SHUFFLED_ORDER_F3")
RELABEL_ARM = "F_RANDOM_RELABEL_F3"
SENTIMENT_ARM = "H_SENTIMENT_LEXICON"


def score_arms(records, Y):
    """Populate every available B1.4b′ arm (rows aligned to the same concept list, same CV
    folds, matched decoder capacity). Pending-source arms are returned explicitly, not
    silently dropped."""
    scores, pending = score_all(records, Y)
    arm_scores, pending_arms = {}, {}
    for a in ARMS:
        if a["key"] in scores:
            arm_scores[a["id"]] = scores[a["key"]]
        else:
            pending_arms[a["id"]] = BASELINE_PENDING_SOURCE     # e.g. H when no sentiment source
    if "sentiment" in pending:
        pending_arms["H_SENTIMENT_LEXICON"] = BASELINE_PENDING_SOURCE
    if "length_frequency" in pending:                            # length present, frequency pending
        pending_arms["G_LENGTH_FREQUENCY"] = "FREQ_" + BASELINE_PENDING_SOURCE
    return arm_scores, pending_arms


def decide_label_arms(arm_scores, flags=None, margin=MARGIN, chance=CHANCE):
    """Terminal label from the ARM scores. A_F3_REAL is the candidate; every other arm is a
    control it must beat. Phonology (B/C) is primary; order (D/E) and relabel (F) co-primary."""
    flags = flags or {}
    strong = chance + margin
    if flags.get("y_not_independent"):
        return "Y_NOT_INDEPENDENT"
    if flags.get("decoder_leak"):
        return "DECODER_LEAKAGE_INVALID"
    if CANDIDATE_ARM not in arm_scores:
        return "INCONCLUSIVE"
    A = arm_scores[CANDIDATE_ARM]
    controls = {k: v for k, v in arm_scores.items() if k != CANDIDATE_ARM}
    if not controls or all(v <= strong for v in arm_scores.values()):
        return "NULL_RETURN_BOTTOM"
    explainers = {k: v for k, v in controls.items() if v >= strong and v >= A - margin}
    if A >= strong and not explainers and (A - max(controls.values()) > margin):
        return "L1_L2_L3_ATTRIBUTE_SIGNAL"
    if explainers.keys() & set(PHONOLOGY_ARMS):
        return "F_COLLAPSES_TO_PHONOLOGY"
    if explainers.keys() & set(ORDER_ARMS):
        return "BAG_OR_SHUFFLE_EXPLAINS"
    if RELABEL_ARM in explainers:
        return "RANDOM_RELABEL_EXPLAINS"
    if SENTIMENT_ARM in explainers:
        return "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS"
    return "INCONCLUSIVE"


def score_run_arms(records, Y, flags=None):
    """Arm-based generic scorer. SYNTHETIC/interface use only — NOT the real evidence run."""
    arm_scores, pending_arms = score_arms(records, Y)
    label = decide_label_arms(arm_scores, flags)
    return {"arm_scores": arm_scores, "pending_arms": pending_arms, "label": label,
            "candidate_arm": CANDIDATE_ARM,
            "primary_control": "B_PHONOLOGY_PLAIN",
            "co_primary_controls": ["D_BAG_OF_PHONEMES", "E_SHUFFLED_ORDER_F3", "F_RANDOM_RELABEL_F3"],
            "arms_are": "predictor_feature_arms_not_llm_prompt_arms"}


# =====================================================================================
# synthetic self-check (NO real McRae Y). Records use the real Stage A′ inventory.
# =====================================================================================
def _rand_records(n, seed, alphabet=None, length=(3, 7), covars=False):
    rng = np.random.default_rng(seed)
    alpha = alphabet or [p for p in INVENTORY]
    recs = []
    for i in range(n):
        L = int(rng.integers(*length))
        recs.append({"phonemes": [alpha[int(rng.integers(len(alpha)))] for _ in range(L)],
                     "covars": ({"freq": float(rng.normal()), "sentiment": float(rng.normal())}
                                if covars else {})})
    return recs


def make_synthetic(regime, n=60, seed=0, ncols=5):
    recs = _rand_records(n, seed, covars=True)
    rng = np.random.default_rng(seed + 7)
    noise = rng.normal(size=(n, ncols))

    def z(v):
        v = np.asarray(v, float); return (v - v.mean()) / (v.std() + 1e-9)

    if regime == "f3":
        base = z(extract_f3(recs)[:, 2])
        Y = np.stack([base * 3 + 0.5 * noise[:, j] for j in range(ncols)], axis=1)
    elif regime == "phonology":
        base = z(extract_phonology(recs)[:, 0])
        Y = np.stack([base * 3 + 0.5 * noise[:, j] for j in range(ncols)], axis=1)
    elif regime == "bag":
        # phonological-twin identity signal: count('a') - count('aa') (same features, distinct identity)
        c = np.array([[r["phonemes"].count("a"), r["phonemes"].count("aa")] for r in recs], float)
        base = z((c[:, 0] - c[:, 1]) / np.maximum(1, [len(r["phonemes"]) for r in recs]))
        Y = np.stack([base * 3 + 0.5 * noise[:, j] for j in range(ncols)], axis=1)
    elif regime == "sentiment":
        base = z([r["covars"]["sentiment"] for r in recs])
        Y = np.stack([base * 3 + 0.5 * noise[:, j] for j in range(ncols)], axis=1)
    elif regime == "null":
        Y = noise
    else:
        raise ValueError(regime)
    return recs, Y


SYNTH_REGIMES = {"f3": "L1_L2_L3_ATTRIBUTE_SIGNAL", "phonology": "F_COLLAPSES_TO_PHONOLOGY",
                 "bag": "BAG_OR_SHUFFLE_EXPLAINS", "sentiment": "SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS",
                 "null": "NULL_RETURN_BOTTOM"}


def run_selfcheck():
    print("B1.4b′ scorer synthetic self-check — PREDICTOR-FEATURE ARMS (NO real McRae Y):")
    print("  arms:", ", ".join(a["id"] for a in ARMS))
    for regime, exp in SYNTH_REGIMES.items():
        recs, Y = make_synthetic(regime)
        res = score_run_arms(recs, Y)
        ok = res["label"] == exp
        top = sorted(res["arm_scores"].items(), key=lambda kv: -kv[1])[:3]
        print(f"  {'OK ' if ok else 'XX '} {regime:10s} -> {res['label']:40s} (expect {exp})  top={top}")
    print("SYNTHETIC ONLY — arms are predictor-feature arms (not B1.3 LLM prompt arms).")
    print("No real evidence run, no real McRae Y, no evidence freeze.")


if __name__ == "__main__":
    run_selfcheck()
