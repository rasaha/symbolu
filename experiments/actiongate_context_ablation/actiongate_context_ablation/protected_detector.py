"""Trainable protected-span detector.

Predicts a 5-class label per unit — ENVELOPE_CRITICAL / DECISION_CRITICAL /
ASSURANCE_CRITICAL / STRUCTURAL / NON_CRITICAL — from paraphrase-robust features
(source type, structural flags, extractor-v2 concept flags, filler markers). It is
a from-scratch multinomial logistic regression (pure Python, deterministic: zero
init, fixed epochs/lr/L2, no randomness) so it needs no external ML dependency.

Labels are NOT invented: they are the deterministic gate-derived criticality from
the existing ActionGate ablation study (annotation.derive_primary), mapped to the
five classes. Training uses DEV+VALIDATION units only; HELDOUT is never trained on.

``protect(ctx)`` returns the set of unit ids predicted != NON_CRITICAL.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import annotation, extractor_v2
from .textnorm import tokens
from .units import SOURCE_TYPES

# 5 target classes (order fixed)
ENVELOPE_CRITICAL = "ENVELOPE_CRITICAL"
DECISION_CRITICAL = "DECISION_CRITICAL"
ASSURANCE_CRITICAL = "ASSURANCE_CRITICAL"
STRUCTURAL = "STRUCTURAL"
NON_CRITICAL = "NON_CRITICAL"
CLASSES = [ENVELOPE_CRITICAL, DECISION_CRITICAL, ASSURANCE_CRITICAL, STRUCTURAL, NON_CRITICAL]

# map annotation.derive_primary output -> target class (deterministic, no relabeling)
_LABEL_MAP = {
    "decision_critical": DECISION_CRITICAL,
    "envelope_critical": ENVELOPE_CRITICAL,
    "assurance_critical": ASSURANCE_CRITICAL,
    "structure_critical": STRUCTURAL,
    "redundant_decision_relevant": DECISION_CRITICAL,  # decision-relevant, duplicated
    "non_critical": NON_CRITICAL,
}

_CONCEPTS = ["artifact", "sim_high", "sim_medium", "backup", "appr_single", "appr_dual",
             "attestation", "sink_approved", "reversibility_cost"]
_FILLER = ("weekly", "sprint", "review", "quarter", "launch", "historical", "log:",
           "previously", "earlier", "no issues", "planning", "on-call", "reliability")
_SRC = sorted(SOURCE_TYPES)


def features(unit) -> list:
    t = unit.text or ""
    tl = t.lower()
    toks = tokens(t)
    ex = extractor_v2.extract_unit(t)
    f = []
    # source-type one-hot (paraphrase-invariant metadata)
    f += [1.0 if unit.source_type == s else 0.0 for s in _SRC]
    # structural flags
    f.append(1.0 if any(c.isdigit() for c in t) else 0.0)
    f.append(1.0 if "{" in t and "}" in t else 0.0)
    f.append(1.0 if "|" in t else 0.0)
    f.append(1.0 if ("://" in t or "sha256:" in t) else 0.0)
    f.append(1.0 if ":" in t or "=" in t else 0.0)
    # extractor-v2 concept flags (structured-or-semantic)
    present = set(ex.concepts) | ({"__struct__"} if ex.structured_keys else set())
    f += [1.0 if c in present else 0.0 for c in _CONCEPTS]
    f.append(1.0 if ex.structured_keys else 0.0)
    f.append(1.0 if ex.uncertain else 0.0)
    # filler markers
    f.append(1.0 if any(w in tl for w in _FILLER) else 0.0)
    # token count (normalized) and redundancy flag
    f.append(min(len(toks), 40) / 40.0)
    f.append(1.0 if unit.redundancy_set else 0.0)
    return f


N_FEATURES = None  # set on first featurize


@dataclass
class Model:
    W: list        # [n_classes][n_features]
    b: list        # [n_classes]

    def predict_class(self, feat) -> str:
        logits = [sum(w * x for w, x in zip(self.W[c], feat)) + self.b[c]
                  for c in range(len(CLASSES))]
        m = max(logits)
        exps = [math.exp(z - m) for z in logits]
        s = sum(exps)
        probs = [e / s for e in exps]
        return CLASSES[max(range(len(CLASSES)), key=lambda i: probs[i])]


def derive_label(run, uid: str) -> str:
    return _LABEL_MAP[annotation.derive_primary(run, uid)]


def build_dataset(items, runs, splits):
    """Return (X, y) over units whose item split is in `splits`."""
    X, y = [], []
    for it, run in zip(items, runs):
        if it.split not in splits:
            continue
        for u in it.context.units:
            X.append(features(u))
            y.append(derive_label(run, u.id))
    return X, y


def train(X, y, *, epochs=400, lr=0.5, l2=1e-3) -> Model:
    nc, nf = len(CLASSES), len(X[0])
    W = [[0.0] * nf for _ in range(nc)]
    b = [0.0] * nc
    yi = [CLASSES.index(lbl) for lbl in y]
    n = len(X)
    for _ in range(epochs):
        gW = [[0.0] * nf for _ in range(nc)]
        gb = [0.0] * nc
        for x, ti in zip(X, yi):
            logits = [sum(W[c][j] * x[j] for j in range(nf)) + b[c] for c in range(nc)]
            m = max(logits)
            exps = [math.exp(z - m) for z in logits]
            s = sum(exps)
            probs = [e / s for e in exps]
            for c in range(nc):
                err = probs[c] - (1.0 if c == ti else 0.0)
                gb[c] += err
                if err:
                    for j in range(nf):
                        if x[j]:
                            gW[c][j] += err * x[j]
        for c in range(nc):
            b[c] -= lr * gb[c] / n
            for j in range(nf):
                W[c][j] -= lr * (gW[c][j] / n + l2 * W[c][j])
    return Model(W=W, b=b)


class TrainedDetector:
    def __init__(self, model: Model):
        self.model = model

    def predict(self, unit) -> str:
        return self.model.predict_class(features(unit))

    def protect(self, ctx) -> set:
        return {u.id for u in ctx.units if self.predict(u) != NON_CRITICAL}


def fit(items, runs, train_splits=("DEV", "VALIDATION")) -> TrainedDetector:
    X, y = build_dataset(items, runs, set(train_splits))
    return TrainedDetector(train(X, y))
