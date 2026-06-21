"""resonance.py — group-aware R (realization strength) for the C×R×S MATCH-filter.

Flat 12D cosine is non-discriminative: all-positive, structured vectors look similar (cosine
0.96-0.999), so R cannot tell domains apart. Group-aware R instead asks *which family of structure
is active* — it compares per-resonance-group emphasis (relative across families), weights groups per
domain, and penalises the domain's blocked lanes being lit:

    R = Σ_g  w_g · group_match_g          (reward: emphasis agreement per resonance group)
        − pen_w · mean(term[blocked_lanes])  (penalty: forbidden lanes too high)

group_match_g = min(tp_g, dp_g) / max(tp_g, dp_g) on L1-normalised group profiles (relative emphasis,
so magnitude collinearity no longer inflates the score). Every call returns a per-group trace.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import numpy as np

from . import registry as REG

PENALTY_WEIGHT = 0.6   # how hard blocked lanes being lit docks R

# S-gate for the phoneme-derived blocked-lane penalty (shared by C and R): only a STRONG semantic
# match relaxes it. S < C_GATE_LO -> no relaxation (penalty intact); S >= C_GATE_HI -> fully relaxed.
C_GATE_LO = 0.35
C_GATE_HI = 0.70


def s_gate_suppression(s) -> float:
    """Fraction by which a strong semantic match S relaxes the phoneme blocked-lane penalty, in [0,1]."""
    if s is None:
        return 0.0
    sc = float(np.clip(s, 0.0, 1.0))
    return float(np.clip((sc - C_GATE_LO) / (C_GATE_HI - C_GATE_LO), 0.0, 1.0))


def group_activations(vec) -> Dict[str, float]:
    """Mean activation of each resonance group for a 12D vector."""
    v = np.asarray(vec, dtype=float)
    return {g: float(np.mean([v[REG.LAYER_INDEX[l]] for l in lanes]))
            for g, lanes in REG.RESONANCE_GROUPS.items()}


def _l1(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(d.values())
    return {k: (v / s if s else 0.0) for k, v in d.items()}


def domain_group_weights(domain: str, template=None) -> Dict[str, float]:
    """Per-domain group weights: explicit override if present, else derived from the template."""
    if domain in REG.DOMAIN_GROUP_WEIGHTS:
        w = {g: float(REG.DOMAIN_GROUP_WEIGHTS[domain].get(g, 0.0)) for g in REG.RESONANCE_GROUPS}
        return _l1(w)
    vec = template if template is not None else REG.DOMAIN_TEMPLATES[domain].vector
    return _l1(group_activations(vec))


def _blocked_lanes(domain: str, template=None):
    if domain in REG.ONTOLOGY_OVERRIDES:
        return REG.ONTOLOGY_OVERRIDES[domain].blocked_high
    if template is not None:
        return REG.derive_ontology_rule(domain, vector=list(np.asarray(template, float))).blocked_high
    return REG.derive_ontology_rule(domain).blocked_high


def realization_grouped(term_vec, domain: str, template=None,
                        penalty_weight: float = PENALTY_WEIGHT, s=None) -> Tuple[float, Dict]:
    """Group-aware R in [0,1] plus a per-group trace.

    `template` lets callers score a domain whose template isn't in the registry (e.g. audits).
    `s` (semantic coherence) S-gates the blocked-lane penalty exactly as in C: a strong semantic match
    relaxes the phoneme-derived penalty so a correct blocked-lane domain isn't crushed; weak S never
    relaxes it (so doctor→fruit stays low). Template-vs-template audits pass s=None (full penalty).
    """
    v = np.asarray(term_vec, dtype=float)
    d_vec = np.asarray(template if template is not None else REG.DOMAIN_TEMPLATES[domain].vector, float)
    tp, dp = _l1(group_activations(v)), _l1(group_activations(d_vec))
    w = domain_group_weights(domain, template)

    groups = {}
    reward = 0.0
    for g in REG.RESONANCE_GROUPS:
        hi, lo = max(tp[g], dp[g]), min(tp[g], dp[g])
        match = (lo / hi) if hi > 0 else 1.0
        contrib = w[g] * match
        reward += contrib
        groups[g] = {"term_emphasis": round(tp[g], 3), "domain_emphasis": round(dp[g], 3),
                     "weight": round(w[g], 3), "match": round(match, 3),
                     "contribution": round(contrib, 4)}

    blocked = _blocked_lanes(domain, template)
    pen_raw = float(np.mean([v[REG.LAYER_INDEX[l]] for l in blocked])) if blocked else 0.0
    supp = s_gate_suppression(s)                       # strong S relaxes the phoneme blocked penalty
    penalty = penalty_weight * pen_raw * (1.0 - supp)
    R = float(np.clip(reward - penalty, 0.0, 1.0))
    trace = {"groups": groups, "reward": round(reward, 4), "blocked_lanes": list(blocked),
             "penalty": round(penalty, 4), "s_suppression": round(supp, 3), "R": round(R, 4)}
    return R, trace


def realization_flat(term_vec, domain: str, template=None) -> float:
    """Legacy flat 12D cosine (kept for comparison/ablation)."""
    v = np.asarray(term_vec, dtype=float)
    d = np.asarray(template if template is not None else REG.DOMAIN_TEMPLATES[domain].vector, float)
    den = (np.linalg.norm(v) * np.linalg.norm(d)) or 1.0
    return float(np.clip(v @ d / den, 0.0, 1.0))
