#!/usr/bin/env python3
"""Frozen protocol configuration for the E1 capability probe.

All values here are FROZEN on non-reserved development fixtures (Stage 2) before any reserved-seed run.
Gate numbers are grounded in the dev calibration (see PROTOCOL_LOCK.md) with margins below observed dev
performance; they are NOT tuned on the reserved final pool.
"""
from __future__ import annotations

import task as T

POOL_SALT = "e1_pool_v1"

# ---- frozen model/train config ---------------------------------------------------------
D = 64
TRAIN_EPISODES = 1500
TRAIN_SEED_FOR_EPISODES = 7
BATCH = 48
LR = 1e-3

# ---- bounded candidate set (frozen in DEV_CALIBRATION_PLAN.md, committed before selection) ----
# each candidate = (steps, tau, train_no_match_frac)
CANDIDATES = {
    "C1": (1200, 0.07, 0.30),
    "C2": (1800, 0.05, 0.30),
    "C3": (1800, 0.05, 0.40),
    "C4": (1500, 0.05, 0.40),
}
MAX_CANDIDATES = 4
# frozen single configuration = the mechanical winner of the selection rule (run_dev_selection.py
# asserts the rule picks this candidate). Selection rule: on dev seed 500, maximize mean held-out
# addressing over {G1,G2,G3,G4,G5,G7} minus a penalty max(0, nomatch_false_accept - 0.30), subject to
# determinism_ok and leakage all_pass; tie-break lower nomatch_false_accept, then fewer steps.
SELECTED = "C3"
STEPS, TAU, TRAIN_NO_MATCH_FRAC = CANDIDATES[SELECTED]

# ---- frozen cohort -------------------------------------------------------------------
DEV_EVAL_N_PER_SPLIT = 150
RESERVED_EVAL_N_PER_SPLIT = 150
DEV_SEED_BASE = 500
# reserved final evaluation seeds: FRESH, previously-unevaluated, disjoint from dev, from V100 seeds
# 28-32, and from the burned set below. Identities drawn from the FINAL(reserved) pool only.
RESERVED_SEEDS = [3140, 3141, 3142, 3143, 3144]
BURNED_SEEDS = [2028, 2029, 2030, 2031, 2032]   # observed in a premature non-preregistered run; NOT the final cohort
RESERVED_SEEDS_REQUIRED_TO_PASS = 4          # of 5
DEV_SEED_FOR_TABLES = 500

# ---- frozen numerical gates (rationale in GATE_RATIONALE.md) --------------------------
# Gates are ABSOLUTE competence bars motivated by the frozen B0 baseline (anonymous slots are at
# chance, ~1/32 = 0.031 addressing) and a meaningful minimum effect size, NOT thresholds set at
# observed dev performance. A partially-generalizing or shortcut model FAILS these bars (see rationale).
GATES = {
    # generalization: min correct-key top-1 addressing accuracy
    "G1_unseen_identity_min_addr": 0.80,
    "G2_paraphrase_min_addr": 0.80,
    "G3_hard_names_min_addr": 0.80,
    "G4_same_entity_diff_attr_min_addr": 0.75,
    "G5_recombined_min_addr": 0.80,
    # no-match (G6)
    "nomatch_max_false_accept": 0.30,
    "nomatch_min_recall": 0.70,
    "nomatch_min_precision": 0.70,
    "nomatch_max_confident_false_accept": 0.20,
    "valid_max_false_reject": 0.15,
    "min_answer_availability": 0.80,
    # end-to-end
    "min_ordinary_retrieval_accuracy": 0.70,     # E1 e2e on G1
    "min_improvement_over_b0": 0.50,             # E1_e2e - B0_e2e on G1
    "min_oracle_key_value_accuracy": 0.99,
    "max_oracle_to_predicted_gap": 0.30,
    "min_G7_stable_addr": 0.90,                  # no catastrophic regression on stable cases
    # fresh-seed reliability
    "worst_seed_min_G1_addr": 0.70,
}

# ---- futility / compute -----------------------------------------------------------------
MAX_STEPS_PER_SEED = STEPS       # bounded
DEV_SEEDS = [500, 501, 502]      # non-reserved development seeds


def build_train_episodes():
    return T.build_split(T.identity_pools(POOL_SALT)["train"], TRAIN_EPISODES,
                         seed=TRAIN_SEED_FOR_EPISODES, no_match_frac=TRAIN_NO_MATCH_FRAC)


def build_dev_eval(seed_base=None):
    return T.build_eval_splits(T.identity_pools(POOL_SALT)["dev"],
                               DEV_EVAL_N_PER_SPLIT, seed_base or DEV_SEED_BASE)


def build_reserved_eval(seed_base):
    """FINAL(reserved) pool only. Called ONLY in Stage 3."""
    return T.build_eval_splits(T.identity_pools(POOL_SALT)["final"],
                               RESERVED_EVAL_N_PER_SPLIT, seed_base)
