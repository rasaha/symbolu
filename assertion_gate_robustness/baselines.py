"""Baselines (Phase 7). Each maps an OBSERVED SignalBundle (+ claim_strength) to a disposition.
Signal-trusting rules (F=G_risk) use observed values directly and thus degrade under noise; the
uncertainty-aware baselines (G/J/K) consult meta-signals. Tunable baselines are fit on the dev
CLEAN split only. Parameter counts are reported (complexity accounting). No live calls.

Includes the from-scratch depth-limited decision tree (L) — no sklearn — and the oracle (O) which
reads TRUE facts as an upper bound. The thin AssertionGate (N) lives in gate.py (Phase 8).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from assertion_gate_robustness.dataset import BaseItem, clean_bundle, split
from assertion_gate_robustness.signals import SignalBundle
from assertion_gate_robustness.taxonomy import Disposition as D, to_primary

_HIGH = ("high", "critical")


def _entail_num(b: SignalBundle) -> float:
    return {"supports": 1.0, "neutral": 0.0, "contradicts": -1.0}[b.entailment.label]


def _features(b: SignalBundle, claim: float) -> List[float]:
    return [b.effective_support(), _entail_num(b), b.evidence.adequacy,
            1.0 if b.high_risk() else 0.0, b.uncertainty(), claim - b.grounding.support]


# --- A: no governance ------------------------------------------------------
def base_A(b, claim): return D.ALLOW.value

# --- B: confidence threshold ----------------------------------------------
def make_B(thr):
    return lambda b, claim: D.ALLOW.value if b.grounding.confidence >= thr else D.INDETERMINATE.value

# --- C: grounding only -----------------------------------------------------
def make_C(hi, lo):
    def f(b, claim):
        s = b.grounding.support
        return D.ALLOW.value if s >= hi else D.REJECT.value if s <= lo else D.INDETERMINATE.value
    return f

# --- D: entailment only ----------------------------------------------------
def base_D(b, claim):
    return {"supports": D.ALLOW.value, "contradicts": D.REJECT.value,
            "neutral": D.INDETERMINATE.value}[b.entailment.label]

# --- E: grounding + entailment (risk-blind) --------------------------------
def make_E(margin):
    def f(b, claim):
        if b.entailment.label == "contradicts":
            return D.REJECT.value
        if b.entailment.label == "neutral":
            return D.INDETERMINATE.value
        return D.ALLOW.value if (claim - b.grounding.support) <= margin else D.QUALIFY.value
    return f

# --- F: G_risk (E + risk rule) — trusts observed signals -------------------
def make_F(margin, big):
    e = make_E(margin)
    def f(b, claim):
        base = e(b, claim)
        if b.high_risk() and b.evidence.conflict == "major":
            return D.ESCALATE.value
        if b.high_risk() and base == D.QUALIFY.value and (claim - b.grounding.support) >= big:
            return D.ESCALATE.value
        return base
    return f

# --- G: abstain on any uncertainty ----------------------------------------
def make_G(thr):
    e = make_E(0.10)
    def f(b, claim):
        if b.uncertainty() >= thr:
            return D.ESCALATE.value if b.high_risk() else D.INDETERMINATE.value
        return e(b, claim)
    return f

# --- H: majority vote ------------------------------------------------------
def base_H(b, claim):
    votes = []
    votes.append(D.ALLOW.value if b.grounding.support >= 0.6 else D.REJECT.value)
    votes.append({"supports": D.ALLOW.value, "contradicts": D.REJECT.value,
                  "neutral": D.INDETERMINATE.value}[b.entailment.label])
    votes.append(D.ESCALATE.value if b.high_risk() and b.uncertainty() > 0.3 else D.ALLOW.value)
    from collections import Counter
    return Counter(votes).most_common(1)[0][0]

# --- I: weighted linear rule (fit on dev) ----------------------------------
def make_I(w):
    def f(b, claim):
        x = _features(b, claim)
        score = sum(wi * xi for wi, xi in zip(w[:len(x)], x)) + w[-1]
        if b.entailment.label == "contradicts":
            return D.REJECT.value
        if score >= 0.6:
            return D.ALLOW.value
        if score >= 0.2:
            return D.QUALIFY.value
        return D.ESCALATE.value if b.high_risk() else D.INDETERMINATE.value
    return f

# --- J: risk-first fail-closed --------------------------------------------
def make_J(unc_thr):
    e = make_E(0.10)
    def f(b, claim):
        if b.high_risk() and b.uncertainty() >= unc_thr:
            return D.ESCALATE.value
        return e(b, claim)
    return f

# --- K: calibrated combination (confidence-discounted posterior) -----------
def make_K(thr, adeq_thr):
    def f(b, claim):
        if b.entailment.label == "contradicts":
            return D.REJECT.value
        post = b.effective_support() * (0.5 + 0.5 * b.entailment.confidence
                                        * (1.0 if b.entailment.label == "supports" else 0.0))
        if b.evidence.adequacy < adeq_thr:
            return D.ESCALATE.value if b.high_risk() else D.INDETERMINATE.value
        if post >= thr and (claim - b.grounding.support) <= 0.12:
            return D.ALLOW.value
        if post >= thr * 0.5:
            return D.QUALIFY.value
        return D.ESCALATE.value if b.high_risk() else D.INDETERMINATE.value
    return f


# --- L: from-scratch depth-2 decision tree (no sklearn) --------------------
class _Tree:
    def __init__(self): self.root = None
    def fit(self, X, y, depth=3):
        self.root = self._build(list(zip(X, y)), depth); return self
    def _majority(self, rows):
        from collections import Counter
        return Counter(r[1] for r in rows).most_common(1)[0][0]
    def _build(self, rows, depth):
        labels = set(r[1] for r in rows)
        if depth == 0 or len(labels) == 1 or len(rows) < 6:
            return {"leaf": self._majority(rows)}
        best = None
        for fi in range(len(rows[0][0])):
            vals = sorted(set(r[0][fi] for r in rows))
            for k in range(1, len(vals)):
                thr = (vals[k - 1] + vals[k]) / 2
                left = [r for r in rows if r[0][fi] <= thr]
                right = [r for r in rows if r[0][fi] > thr]
                if not left or not right:
                    continue
                imp = (len(left) * self._gini(left) + len(right) * self._gini(right)) / len(rows)
                if best is None or imp < best[0]:
                    best = (imp, fi, thr, left, right)
        if best is None:
            return {"leaf": self._majority(rows)}
        _, fi, thr, left, right = best
        return {"fi": fi, "thr": thr, "L": self._build(left, depth - 1), "R": self._build(right, depth - 1)}
    def _gini(self, rows):
        from collections import Counter
        n = len(rows); c = Counter(r[1] for r in rows)
        return 1 - sum((v / n) ** 2 for v in c.values())
    def predict(self, x):
        node = self.root
        while "leaf" not in node:
            node = node["L"] if x[node["fi"]] <= node["thr"] else node["R"]
        return node["leaf"]
    def n_nodes(self):
        def count(n): return 1 if "leaf" in n else 1 + count(n["L"]) + count(n["R"])
        return count(self.root)


def make_L():
    dev = split("dev")
    X = [_features(clean_bundle(it), it.claim_strength) for it in dev]
    y = [to_primary(it.gold) for it in dev]
    tree = _Tree().fit(X, y, depth=3)
    fn = lambda b, claim: tree.predict(_features(b, claim))
    fn._n_params = tree.n_nodes()
    return fn


# --- O: oracle (reads TRUE facts) -----------------------------------------
def oracle(it: BaseItem) -> str:
    return it.gold


# --- tuning ----------------------------------------------------------------
def _agree_clean(fn, items):
    ok = sum(1 for it in items if to_primary(fn(clean_bundle(it), it.claim_strength)) == to_primary(it.gold))
    return ok / len(items)


def build_all() -> Tuple[Dict[str, Callable], Dict[str, int]]:
    dev = split("dev")
    B = max([i/20 for i in range(21)], key=lambda t: _agree_clean(make_B(t), dev))
    C = max([(hi, lo) for hi in [i/20 for i in range(10,21)] for lo in [i/20 for i in range(0,11)]],
            key=lambda hl: _agree_clean(make_C(*hl), dev))
    E = max([i/20 for i in range(11)], key=lambda m: _agree_clean(make_E(m), dev))
    F = max([(m, g) for m in [i/20 for i in range(11)] for g in [i/10 for i in range(2,7)]],
            key=lambda mg: _agree_clean(make_F(*mg), dev))
    G = max([i/20 for i in range(4, 18)], key=lambda t: _agree_clean(make_G(t), dev))
    J = max([i/20 for i in range(4, 18)], key=lambda t: _agree_clean(make_J(t), dev))
    K = max([(t, a) for t in [i/20 for i in range(6,18)] for a in [i/20 for i in range(4,12)]],
            key=lambda ta: _agree_clean(make_K(*ta), dev))
    # I: coarse weight search (small grid on the two dominant features)
    Iw = max([[ws, we, 0, 0, 0, 0, wb] for ws in [0.4,0.6,0.8] for we in [0.2,0.4] for wb in [-0.1,0.0,0.1]],
             key=lambda w: _agree_clean(make_I(w), dev))
    L = make_L()
    methods = {"A_none": base_A, "B_confidence": make_B(B), "C_grounding": make_C(*C),
               "D_entailment": base_D, "E_ground_entail": make_E(E), "F_g_risk": make_F(*F),
               "G_abstain": make_G(G), "H_majority": base_H, "I_weighted": make_I(Iw),
               "J_risk_first": make_J(J), "K_calibrated": make_K(*K), "L_tree": L}
    params = {"A_none": 0, "B_confidence": 1, "C_grounding": 2, "D_entailment": 0,
              "E_ground_entail": 1, "F_g_risk": 2, "G_abstain": 1, "H_majority": 0,
              "I_weighted": 7, "J_risk_first": 1, "K_calibrated": 2, "L_tree": getattr(L, "_n_params", 0)}
    return methods, params
