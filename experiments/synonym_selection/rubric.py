"""Target → vṛtti rubric bridge (Version-A; scaffolding only).

This is the **weakest link** of the synonym-selection pilot (PREREG_SYNONYM_SELECTION.md
§5/§13): a frozen, name-blind rubric that mechanically maps coded TRAIT ratings of a target
sense into a vṛtti vector. Coders rate traits (never vṛttis); the rubric does the rest.

Rubric A is dispositive; Rubric B is an independently-authored sensitivity check
(B can only DOWNGRADE an A-pass to RUBRIC_DEPENDENT — it can never rescue an A-fail).

**Modularity / Version B.** This whole module is the swappable `target → vṛtti` bridge.
A future **Version B** removes it entirely (pairwise human acoustic-quality judgments →
target ordering directly), so downstream code depends only on the *output* (per-target
profiles or orderings), never on this rubric. Keep that boundary clean.

Synthetic placeholders only — no real trait inventory, no real target/synonym data,
no fit, no semantic claim.
"""
from __future__ import annotations

import numpy as np

from reliability import reliability_gate, FLOOR

# --- SYNTHETIC placeholders (real inventories are authored & frozen at pre-registration) ---
TRAIT_INVENTORY = ["t_intensity", "t_hardness", "t_brightness"]   # placeholder trait dims
VRTTI_VOCAB = ["v0", "v1", "v2", "v3"]                            # placeholder vṛtti space


def make_rubric(weights: dict[str, list[float]]) -> np.ndarray:
    """Rubric = matrix [n_traits x n_vrtti]; weights maps trait -> vṛtti weight vector."""
    return np.array([weights[t] for t in TRAIT_INVENTORY], dtype=float)


def target_profiles(agg_ratings, rubric: np.ndarray) -> np.ndarray:
    """Mechanical aggregation: [n_targets x n_traits] @ [n_traits x n_vrtti] -> [n_targets x n_vrtti]."""
    return np.asarray(agg_ratings, float) @ rubric


def _aggregate(insider, naive) -> np.ndarray:
    """Combine both pools' coders -> per-target trait means [n_targets x n_traits]."""
    both = np.concatenate([np.asarray(insider, float), np.asarray(naive, float)], axis=2)
    return both.mean(axis=2)


def bridge(insider, naive, rubric_A: np.ndarray, rubric_B: np.ndarray,
           floor: float = FLOOR) -> dict:
    """Run the reliability gate, then (if OK) produce target profiles under Rubric A and B.

    insider/naïve : [n_targets, n_traits, n_coders] synthetic trait ratings (one pool each).
    Returns {status, alpha_*, profiles_A, profiles_B}. profiles_* is None unless status OK.
    """
    gate = reliability_gate(insider, naive, floor)
    out = dict(gate)
    if gate["status"] != "OK":
        out["profiles_A"] = out["profiles_B"] = None
        return out
    agg = _aggregate(insider, naive)
    out["profiles_A"] = target_profiles(agg, rubric_A)
    out["profiles_B"] = target_profiles(agg, rubric_B)
    return out


def rubric_verdict(a_pass: bool, b_pass: bool) -> str:
    """Rubric A dispositive; B sensitivity only (PREREG §9).

    - A fails              -> RUBRIC_A_FAIL  (A's null stands; B cannot rescue)
    - A passes, B passes   -> RUBRIC_A_AND_B_PASS
    - A passes, B fails    -> RUBRIC_DEPENDENT (non-confirmation, not a partial win)
    """
    if not a_pass:
        return "RUBRIC_A_FAIL"
    return "RUBRIC_A_AND_B_PASS" if b_pass else "RUBRIC_DEPENDENT"
