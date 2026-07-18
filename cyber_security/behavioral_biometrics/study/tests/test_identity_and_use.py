"""Identity ablation (fairness, leakage, no-IDs) + USE machinery."""

from __future__ import annotations

import numpy as np

from cyber_security.behavioral_biometrics import splits
from cyber_security.behavioral_biometrics.study import arms, identity, mockdata, use_eval
from cyber_security.behavioral_biometrics.study.effects import DEFAULT

CFG = DEFAULT


def _recs(regime, seed=1):
    return mockdata.make_cohort(regime, seed=seed)["records"]


def test_ablation_runs_all_arms_same_split():
    recs = _recs("MULTIMODAL_MARGINAL_SIGNAL")
    plan = splits.session_disjoint(recs, seed=1)
    assert splits.check_leakage(plan, recs) == []
    ab = identity.run_ablation(recs, plan, cfg=CFG)
    for a in ("K", "P", "MM", "MM_SHUFFLED", "MM_COUPLING", "MM_COUPLING_CONTEXT"):
        assert ab[a]["usable"]


def test_no_signal_is_chance():
    recs = _recs("NO_SIGNAL")
    plan = splits.session_disjoint(recs, seed=1)
    auc = identity.run_arm(recs, plan, "MM", cfg=CFG)["metrics"]["auc"]
    assert 0.35 < auc < 0.65


def test_identifiers_not_in_arm_features():
    recs = mockdata.make_cohort("KEYBOARD_ONLY_SIGNAL", seed=1)["records"]
    builder = arms.builder_for("MM_COUPLING")
    feats = builder(recs[0])
    joined = " ".join(feats.keys())
    for ident in ("participant", "device_id", "session_id", "mockP"):
        assert ident not in joined


def test_run_arm_scores_align_across_arms():
    recs = _recs("MULTIMODAL_MARGINAL_SIGNAL")
    plan = splits.session_disjoint(recs, seed=1)
    a = identity.run_arm(recs, plan, "MM", cfg=CFG)
    b = identity.run_arm(recs, plan, "MM_COUPLING", cfg=CFG)
    assert a["labels"] == b["labels"]  # same test rows -> paired contrasts valid


def test_use_coupling_only_beats_controls():
    recs = _recs("COUPLING_ONLY_SIGNAL")
    u = use_eval.run_use(recs, cfg=CFG, iters=300)
    assert u["gain_context_vs_marginal"]["lo"] > 0
    assert u["gain_context_vs_shuffled"]["lo"] > 0
    assert use_eval.classify_use(u, CFG) == use_eval.USER_SPECIFIC_COUPLING_SUPPORTED


def test_use_sampling_artifact_detected():
    recs = _recs("SAMPLING_ARTIFACT")
    u = use_eval.run_use(recs, cfg=CFG, iters=300)
    assert use_eval.classify_use(u, CFG) == use_eval.SAMPLING_OR_CONTEXT_ARTIFACT


def test_use_no_credit_for_extra_modalities():
    # multimodal MARGINAL signal, NO coupling -> coupling features are noise; USE must
    # NOT be credited just because more feature slots exist.
    recs = _recs("MULTIMODAL_MARGINAL_SIGNAL")
    u = use_eval.run_use(recs, cfg=CFG, iters=300)
    assert use_eval.classify_use(u, CFG) != use_eval.USER_SPECIFIC_COUPLING_SUPPORTED


def test_use_no_signal_not_supported():
    recs = _recs("NO_SIGNAL")
    u = use_eval.run_use(recs, cfg=CFG, iters=300)
    assert use_eval.classify_use(u, CFG) in (
        use_eval.COUPLING_NOT_SUPPORTED, use_eval.SAMPLING_OR_CONTEXT_ARTIFACT)


def test_use_classify_branches_pure():
    def u(shuf, marg, ctx=None):
        ci = lambda lo: {"lo": lo, "point": lo + 0.02, "hi": lo + 0.04}
        return {"usable": True, "gain_context_vs_marginal": ci(marg),
                "gain_context_vs_shuffled": ci(shuf), "device": {"assessable": False},
                "false_challenge_increase": 0.0}
    assert use_eval.classify_use(u(0.05, 0.05), CFG) == use_eval.USER_SPECIFIC_COUPLING_SUPPORTED
    assert use_eval.classify_use(u(0.05, 0.01), CFG) == use_eval.USER_SPECIFIC_COUPLING_SMALL_EFFECT
    assert use_eval.classify_use(u(0.05, -0.02), CFG) == use_eval.HUMANNESS_SIGNAL_ONLY
    assert use_eval.classify_use(u(-0.02, 0.05), CFG) == use_eval.SAMPLING_OR_CONTEXT_ARTIFACT
    assert use_eval.classify_use(u(-0.02, -0.02), CFG) == use_eval.COUPLING_NOT_SUPPORTED
    # device-bound
    du = u(0.05, 0.05)
    du["device"] = {"assessable": True, "cross_device_auc": 0.5}
    assert use_eval.classify_use(du, CFG) == use_eval.DEVICE_BOUND_COUPLING_ONLY
